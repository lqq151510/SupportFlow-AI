package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import com.lqq.supportflow.conversation.infrastructure.events.InMemoryGenerationEventStore;
import org.junit.jupiter.api.Test;

class InMemoryGenerationEventStoreTest {
    @Test
    void appendsEachEventTypeOnlyOnceAndReplaysAfterCursor() {
        InMemoryGenerationEventStore store = new InMemoryGenerationEventStore();
        store.appendIfAbsent(1L, "generation.queued", "{}");
        store.appendIfAbsent(1L, "generation.queued", "{}");
        store.appendIfAbsent(1L, "text.delta", "{\"text\":\"hello\"}");
        assertThat(store.readAfter(1L, null)).hasSize(2);
        assertThat(store.readAfter(1L, "1")).singleElement().extracting("type").isEqualTo("text.delta");
    }
}
