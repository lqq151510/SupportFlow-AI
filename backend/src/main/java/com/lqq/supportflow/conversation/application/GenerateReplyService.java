package com.lqq.supportflow.conversation.application;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.action.ToolExecutionService;
import com.lqq.supportflow.conversation.GenerationRequestedEvent;
import com.lqq.supportflow.conversation.domain.GenerationEventStore;
import com.lqq.supportflow.model.ModelChatService;
import com.lqq.supportflow.model.ModelStreamEvent;
import com.lqq.supportflow.model.ModelTool;
import com.lqq.supportflow.knowledge.KnowledgeRetrievalService;
import com.lqq.supportflow.knowledge.RetrievedCitation;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import com.lqq.supportflow.shared.TenantContext;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.net.SocketTimeoutException;
import java.util.concurrent.TimeoutException;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.event.TransactionalEventListener;
import org.springframework.web.reactive.function.client.WebClientResponseException;

@Service
public class GenerateReplyService {
    private final GenerationLifecycleService lifecycle; private final GenerationEventStore events; private final ModelChatService models; private final ToolExecutionService tools; private final KnowledgeRetrievalService knowledge; private final ObjectMapper json;
    public GenerateReplyService(GenerationLifecycleService lifecycle, GenerationEventStore events, ModelChatService models, ToolExecutionService tools, KnowledgeRetrievalService knowledge, ObjectMapper json) { this.lifecycle = lifecycle; this.events = events; this.models = models; this.tools = tools; this.knowledge = knowledge; this.json = json; }

    @Async("generationExecutor")
    @TransactionalEventListener
    public void generate(GenerationRequestedEvent request) {
        TenantContext.set(new AuthenticatedPrincipal(request.customerId(), request.tenantId(), 0L, "CUSTOMER"));
        try {
            if (!lifecycle.start(request)) return;
            long startedAt = System.nanoTime();
            List<RetrievedCitation> citations = knowledge.retrieve(request.tenantId(), request.content());
            if (citations.isEmpty()) { events.appendIfAbsent(request.tenantId(), request.generationId(), "knowledge.insufficient", "{\"reason\":\"NO_TENANT_EVIDENCE\"}"); lifecycle.handoff(request, "knowledge evidence is insufficient"); return; }
            events.append(request.tenantId(), request.generationId(), "knowledge.citations", json.writeValueAsString(citations));
            GenerationAttempt outcome = null;
            for (int attempt = 0; attempt < 2; attempt++) {
                GenerationAttempt current = new GenerationAttempt();
                try {
                    consume(request, citations, current);
                    outcome = current;
                    break;
                } catch (RuntimeException exception) {
                    if (attempt == 0 && !current.toolExecuted && retryable(exception)) {
                        events.append(request.tenantId(), request.generationId(), "generation.reset", "{\"reason\":\"MODEL_RETRY\"}");
                        continue;
                    }
                    throw exception;
                }
            }
            if (outcome == null) throw new IllegalStateException("model retry did not complete");
            if (outcome.failed || outcome.requiresApproval) lifecycle.handoff(request, outcome.failed ? "model generation failed" : "high-risk action requires approval");
            else lifecycle.complete(request, outcome.response.toString(), outcome.inputTokens, outcome.outputTokens, (System.nanoTime() - startedAt) / 1_000_000);
        } catch (Exception exception) {
            events.appendIfAbsent(request.tenantId(), request.generationId(), "model.failed", "{\"code\":\"MODEL_UNAVAILABLE\"}");
            lifecycle.handoff(request, "model generation failed");
        } finally { TenantContext.clear(); }
    }

    private void consume(GenerationRequestedEvent request, List<RetrievedCitation> citations, GenerationAttempt state) throws Exception {
        for (ModelStreamEvent event : models.stream(request.tenantId(), messages(request.content(), citations), supportedTools()).toIterable()) {
            events.append(request.tenantId(), request.generationId(), event.type(), event.data());
            if ("text.delta".equals(event.type())) state.response.append(json.readTree(event.data()).path("text").asText());
            if ("tool.started".equals(event.type())) start(state.calls, event.data());
            if ("tool.arguments.delta".equals(event.type())) appendArguments(state.calls, event.data());
            if ("tool.completed".equals(event.type())) { state.toolExecuted = true; state.requiresApproval |= executeTool(request, state.calls, event.data()); }
            if ("usage.reported".equals(event.type())) { JsonNode usage = json.readTree(event.data()); state.inputTokens = usage.path("inputTokens").asInt(state.inputTokens); state.outputTokens = usage.path("outputTokens").asInt(state.outputTokens); }
            if ("model.failed".equals(event.type())) state.failed = true;
        }
    }

    private boolean retryable(Throwable exception) {
        for (Throwable current = exception; current != null && current != current.getCause(); current = current.getCause()) {
            if (current instanceof TimeoutException || current instanceof SocketTimeoutException) return true;
            if (current instanceof WebClientResponseException response && response.getStatusCode().is5xxServerError()) return true;
        }
        return false;
    }

    private void start(Map<String, ToolCall> calls, String data) throws Exception { JsonNode node = json.readTree(data); calls.put(node.path("callId").asText(), new ToolCall(node.path("name").asText())); }
    private void appendArguments(Map<String, ToolCall> calls, String data) throws Exception { JsonNode node = json.readTree(data); ToolCall call = calls.get(node.path("callId").asText()); if (call != null) call.arguments.append(node.path("argumentsDelta").asText()); }
    private boolean executeTool(GenerationRequestedEvent request, Map<String, ToolCall> calls, String data) throws Exception { ToolCall call = calls.get(json.readTree(data).path("callId").asText()); if (call == null) return false; @SuppressWarnings("unchecked") Map<String, Object> arguments = json.convertValue(json.readTree(call.arguments.toString()), Map.class); var result = tools.execute(request.tenantId(), request.customerId(), call.name, arguments); events.append(request.tenantId(), request.generationId(), "tool.result", json.writeValueAsString(result)); return "PENDING_APPROVAL".equals(result.status()); }
    private List<ModelTool> supportedTools() { Map<String, Object> schema = Map.of("type", "object", "properties", Map.of("orderNo", Map.of("type", "string")), "required", List.of("orderNo"), "additionalProperties", false); return List.of(new ModelTool("order.lookup", "Look up the customer's order.", schema), new ModelTool("shipment.track", "Track a customer shipment.", schema), new ModelTool("refund.checkEligibility", "Check whether an order can be refunded.", schema), new ModelTool("refund.request", "Request a refund; requires human approval.", schema), new ModelTool("compensation.issue", "Issue compensation; requires human approval.", schema)); }
    private List<ModelChatService.ChatMessage> messages(String customerMessage, List<RetrievedCitation> citations) { if (citations.isEmpty()) return List.of(new ModelChatService.ChatMessage("user", customerMessage)); String context = citations.stream().map(citation -> "[" + citation.rank() + "] " + citation.content()).collect(java.util.stream.Collectors.joining("\n")); return List.of(new ModelChatService.ChatMessage("system", "Use the following tenant-scoped knowledge when relevant. Cite sources as [number].\n" + context), new ModelChatService.ChatMessage("user", customerMessage)); }
    private static final class ToolCall { private final String name; private final StringBuilder arguments = new StringBuilder(); private ToolCall(String name) { this.name = name; } }
    private static final class GenerationAttempt { private final StringBuilder response = new StringBuilder(); private final Map<String, ToolCall> calls = new LinkedHashMap<>(); private boolean failed; private boolean requiresApproval; private boolean toolExecuted; private int inputTokens; private int outputTokens; }
}
