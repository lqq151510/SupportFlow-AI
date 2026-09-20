package com.lqq.supportflow.knowledge.application;

import com.lqq.supportflow.knowledge.domain.KnowledgeChunk;
import com.lqq.supportflow.knowledge.domain.KnowledgeChunkPort;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocument;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocumentPort;
import com.lqq.supportflow.model.ModelChatService;
import com.lqq.supportflow.model.ModelStreamEvent;
import com.lqq.supportflow.model.ModelUsageService;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class KnowledgeOrganizerService {

    private final KnowledgeDocumentPort documentPort;
    private final KnowledgeChunkPort chunkPort;
    private final ModelChatService chatService;
    private final ModelUsageService usageService;
    private final boolean mockEnabled;

    public KnowledgeOrganizerService(
            KnowledgeDocumentPort documentPort,
                KnowledgeChunkPort chunkPort,
                ModelChatService chatService,
                @Autowired(required = false) ModelUsageService usageService) {
        this(documentPort, chunkPort, chatService, usageService, false);
    }

    @Autowired
    public KnowledgeOrganizerService(
            KnowledgeDocumentPort documentPort,
            KnowledgeChunkPort chunkPort,
            ModelChatService chatService,
            @Autowired(required = false) ModelUsageService usageService,
            @Value("${supportflow.model.mock.enabled:false}") boolean mockEnabled) {
        this.documentPort = documentPort;
        this.chunkPort = chunkPort;
        this.chatService = chatService;
        this.usageService = usageService;
        this.mockEnabled = mockEnabled;
    }

    @Transactional
    public OrganizedKnowledgeResult organize(Long tenantId, Long knowledgeBaseId, Long documentId) {
        KnowledgeDocument document = documentPort.findById(tenantId, knowledgeBaseId, documentId)
                .orElseThrow(() -> new IllegalArgumentException("knowledge document not found"));

        List<KnowledgeChunk> chunks = chunkPort.findByDocument(tenantId, knowledgeBaseId, documentId);
        String sampleContent = chunks.stream()
                .map(KnowledgeChunk::content)
                .limit(5)
                .collect(Collectors.joining("\n\n"));

        if (sampleContent.isBlank()) {
            sampleContent = "文档：" + document.fileName();
        }

        String modelName = mockEnabled ? "本地规则抽取（Mock，未调用模型）" : chatService.findKnowledgeModelName(tenantId);
        String protocol = mockEnabled ? "LOCAL_EXTRACTOR" : chatService.findKnowledgeProtocol(tenantId);

        long startedAt = System.nanoTime();
        String summary;
        List<String> tags = new ArrayList<>();
        int inputTokens = Math.max(1, sampleContent.length() / 4);
        int outputTokens = 0;

        if (mockEnabled) {
            summary = localSummary(sampleContent, document.fileName());
            tags = defaultTags(document.fileName(), sampleContent);
            long latencyMs = (System.nanoTime() - startedAt) / 1_000_000;
            return new OrganizedKnowledgeResult(document.id(), document.fileName(), summary, tags, modelName, 0, latencyMs);
        }

        try {
            String prompt = "请对以下客服知识库文档内容进行整理，输出结构如下：\n【摘要】200字以内的核心内容提炼\n【标签】3到5个以逗号分隔的分类或业务关键词\n\n文档内容：\n" + sampleContent;
            List<ModelChatService.ChatMessage> messages = List.of(
                    new ModelChatService.ChatMessage("system", "你是一名企业级电商客服与售后知识库整理专家。"),
                    new ModelChatService.ChatMessage("user", prompt)
            );

            StringBuilder responseBuilder = new StringBuilder();
            for (ModelStreamEvent event : chatService.stream(tenantId, messages).toIterable()) {
                if ("text.delta".equals(event.type())) {
                    try {
                        com.fasterxml.jackson.databind.JsonNode node = new com.fasterxml.jackson.databind.ObjectMapper().readTree(event.data());
                        responseBuilder.append(node.path("text").asText(""));
                    } catch (Exception ignored) { }
                }
                if ("usage.reported".equals(event.type())) {
                    try {
                        com.fasterxml.jackson.databind.JsonNode usage = new com.fasterxml.jackson.databind.ObjectMapper().readTree(event.data());
                        inputTokens = usage.path("inputTokens").asInt(inputTokens);
                        outputTokens = usage.path("outputTokens").asInt(outputTokens);
                    } catch (Exception ignored) { }
                }
            }
            String rawText = responseBuilder.toString().trim();
            if (!rawText.isBlank()) {
                summary = extractSummary(rawText, sampleContent);
                tags = extractTags(rawText, document.fileName());
            } else {
                throw new IllegalStateException("knowledge organizer returned no content");
            }
        } catch (Exception modelError) {
            throw new IllegalStateException("knowledge organizer model failed", modelError);
        }

        long latencyMs = (System.nanoTime() - startedAt) / 1_000_000;
        if (usageService != null) {
            usageService.recordUsage(tenantId, "KNOWLEDGE_ORGANIZATION", modelName, protocol, inputTokens, outputTokens, latencyMs);
        }

        return new OrganizedKnowledgeResult(
                document.id(),
                document.fileName(),
                summary,
                tags,
                modelName,
                inputTokens + outputTokens,
                latencyMs
        );
    }

    private String extractSummary(String rawText, String fallback) {
        if (rawText.contains("【摘要】")) {
            int start = rawText.indexOf("【摘要】") + 4;
            int end = rawText.contains("【标签】") ? rawText.indexOf("【标签】") : rawText.length();
            String sub = rawText.substring(start, end).trim();
            if (!sub.isBlank()) return sub;
        }
        return rawText.length() > 300 ? rawText.substring(0, 300) + "…" : rawText;
    }

    private List<String> extractTags(String rawText, String fileName) {
        if (rawText.contains("【标签】")) {
            int start = rawText.indexOf("【标签】") + 4;
            String tagSection = rawText.substring(start).trim();
            return Arrays.stream(tagSection.split("[,，、\n]+"))
                    .map(String::trim)
                    .filter(s -> !s.isBlank())
                    .limit(5)
                    .toList();
        }
        return defaultTags(fileName);
    }

    private String localSummary(String sampleContent, String fileName) {
        String clean = sampleContent.replaceAll("\\s+", " ").trim();
        return clean.length() > 180 ? clean.substring(0, 180) + "…" : "包含「" + fileName + "」的售后服务指引与规范说明。";
    }

    private List<String> defaultTags(String fileName) {
        return defaultTags(fileName, "");
    }

    private List<String> defaultTags(String fileName, String sampleContent) {
        List<String> list = new ArrayList<>();
        list.add("知识文档");
        String source = fileName + " " + sampleContent;
        if (source.contains("退款") || source.contains("退货")) list.add("退款售后");
        if (source.contains("运费") || source.contains("物流") || source.contains("配送")) list.add("物流运费");
        if (source.contains("SLA") || source.contains("工单") || source.contains("时效")) list.add("SLA规范");
        if (source.contains("换货") || source.contains("维修")) list.add("售后服务");
        list.add("售后服务");
        return list.stream().distinct().toList();
    }

    public record OrganizedKnowledgeResult(
            @com.fasterxml.jackson.databind.annotation.JsonSerialize(using = com.fasterxml.jackson.databind.ser.std.ToStringSerializer.class) Long documentId,
            String fileName,
            String summary,
            List<String> tags,
            String modelUsed,
            int totalTokens,
            long latencyMs) {
    }
}
