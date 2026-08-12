package com.lqq.supportflow.model.infrastructure.protocol;

import com.lqq.supportflow.model.domain.ChatModelGateway;
import com.lqq.supportflow.model.domain.ChatModelRequest;
import com.lqq.supportflow.model.domain.EmbeddingGateway;
import com.lqq.supportflow.model.domain.EmbeddingRequest;
import com.lqq.supportflow.model.domain.ModelEvent;
import java.util.List;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

@Component
@ConditionalOnProperty(prefix = "supportflow.model.mock", name = "enabled", havingValue = "true")
public class MockModelGateway implements ChatModelGateway, EmbeddingGateway {

    @Override
    public Flux<ModelEvent> stream(ChatModelRequest request) {
        return Flux.just(
                new ModelEvent.TextDelta("模拟模型已根据租户知识库完成回答。"),
                new ModelEvent.UsageReported(16, 12),
                new ModelEvent.ModelCompleted());
    }

    @Override
    public List<float[]> embedBatch(EmbeddingRequest request) {
        return request.inputs().stream().map(this::embedding).toList();
    }

    private float[] embedding(String input) {
        int hash = input == null ? 0 : input.hashCode();
        return new float[] {1F, (hash & 0xffff) / 65535F, ((hash >>> 16) & 0xffff) / 65535F};
    }
}
