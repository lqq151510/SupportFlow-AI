package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;

import com.lqq.supportflow.model.domain.ChatModelRequest;
import com.lqq.supportflow.model.domain.EmbeddingRequest;
import com.lqq.supportflow.model.domain.ModelEvent;
import com.lqq.supportflow.model.infrastructure.protocol.MockModelGateway;
import java.util.List;
import org.junit.jupiter.api.Test;

class MockModelGatewayTest {

    @Test
    void returnsDeterministicEmbeddingsAndACompletedChatStream() {
        MockModelGateway gateway = new MockModelGateway();

        assertThat(gateway.embedBatch(new EmbeddingRequest(7L, List.of("same", "same", "different"))))
                .satisfies(vectors -> {
                    assertThat(vectors).hasSize(3);
                    assertThat(vectors.get(0)).containsExactly(vectors.get(1));
                    assertThat(vectors.get(0)).isNotEqualTo(vectors.get(2));
                });
        assertThat(gateway.stream(new ChatModelRequest(7L, List.of(), List.of())).collectList().block())
                .anyMatch(ModelEvent.TextDelta.class::isInstance)
                .endsWith(new ModelEvent.ModelCompleted());
    }
}
