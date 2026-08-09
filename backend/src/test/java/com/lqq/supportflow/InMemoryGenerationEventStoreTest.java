package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import com.lqq.supportflow.conversation.infrastructure.events.InMemoryGenerationEventStore;
import org.junit.jupiter.api.Test;

class InMemoryGenerationEventStoreTest {
    @Test
    void deduplicatesStateEventsButRetainsEveryTextDeltaAndReplaysAfterCursor() {
        InMemoryGenerationEventStore store = new InMemoryGenerationEventStore();
        store.appendIfAbsent(1L, "generation.queued", "{}");
        store.appendIfAbsent(1L, "generation.queued", "{}");
        store.append(1L, "text.delta", "{\"text\":\"hello\"}");
        store.append(1L, "text.delta", "{\"text\":\" world\"}");
        assertThat(store.readAfter(1L, null)).hasSize(3);
        assertThat(store.readAfter(1L, "1")).extracting("type").containsExactly("text.delta", "text.delta");
    }
}
