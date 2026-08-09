package com.lqq.supportflow.model.infrastructure.protocol;

import com.lqq.supportflow.model.domain.ChatModelConfig;
import com.lqq.supportflow.model.domain.ChatModelGateway;
import com.lqq.supportflow.model.domain.ChatModelRequest;
import com.lqq.supportflow.model.domain.ModelConfigPort;
import com.lqq.supportflow.model.domain.ModelEvent;
import com.lqq.supportflow.model.domain.ModelProtocol;
import com.lqq.supportflow.model.domain.ModelSecretPort;
import java.util.List;
import java.util.Map;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

@Component
public class ConfiguredChatModelGateway implements ChatModelGateway {
    private final ModelConfigPort configs;
    private final ModelSecretPort secrets;
    private final WebClient client;
    private final OpenAiCompatibleEventNormalizer openAi;
    private final AnthropicMessagesEventNormalizer anthropic;

    public ConfiguredChatModelGateway(ModelConfigPort configs, ModelSecretPort secrets, WebClient.Builder builder,
            OpenAiCompatibleEventNormalizer openAi, AnthropicMessagesEventNormalizer anthropic) {
        this.configs = configs; this.secrets = secrets; this.client = builder.build(); this.openAi = openAi; this.anthropic = anthropic;
    }

    @Override
    public Flux<ModelEvent> stream(ChatModelRequest request) {
        ChatModelConfig config = configs.findDefaultChat(request.tenantId())
                .orElseThrow(() -> new IllegalArgumentException("default chat model is not configured"));
        return config.protocol() == ModelProtocol.OPENAI_COMPATIBLE ? openAi(config, request) : anthropic(config, request);
    }

    private Flux<ModelEvent> openAi(ChatModelConfig config, ChatModelRequest request) {
        return openAi.normalize(client.post().uri(path(config.baseUrl(), "chat/completions"))
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + secrets.decrypt(config.encryptedApiKey()))
                .accept(MediaType.TEXT_EVENT_STREAM)
                .bodyValue(Map.of("model", config.modelName(), "stream", true, "messages", messages(request.messages())))
                .retrieve().bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() { })
                .map(ServerSentEvent::data).filter(data -> data != null));
    }

    private Flux<ModelEvent> anthropic(ChatModelConfig config, ChatModelRequest request) {
        return anthropic.normalize(client.post().uri(path(config.baseUrl(), "v1/messages"))
                .header("x-api-key", secrets.decrypt(config.encryptedApiKey())).header("anthropic-version", "2023-06-01")
                .accept(MediaType.TEXT_EVENT_STREAM)
                .bodyValue(Map.of("model", config.modelName(), "stream", true, "max_tokens", 1024, "messages", messages(request.messages())))
                .retrieve().bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() { })
                .map(frame -> new AnthropicMessagesEventNormalizer.AnthropicSseFrame(frame.event(), frame.data())));
    }

    private List<Map<String, String>> messages(List<ChatModelRequest.ChatMessage> messages) { return messages.stream().map(message -> Map.of("role", message.role(), "content", message.content())).toList(); }
    private String path(String baseUrl, String suffix) { return (baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl) + "/" + suffix; }
}
