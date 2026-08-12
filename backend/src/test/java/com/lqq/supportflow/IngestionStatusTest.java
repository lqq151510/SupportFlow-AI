package com.lqq.supportflow;
import static org.assertj.core.api.Assertions.assertThat;
import com.lqq.supportflow.knowledge.domain.IngestionStatus; import org.junit.jupiter.api.Test;
class IngestionStatusTest {
    @Test
    void onlyAllowsTheDeclaredForwardTransitionsFailureAndRetry() {
        assertThat(IngestionStatus.UPLOADED.canTransitionTo(IngestionStatus.PARSING)).isTrue();
        assertThat(IngestionStatus.UPLOADED.canTransitionTo(IngestionStatus.FAILED)).isTrue();
        assertThat(IngestionStatus.PARSING.canTransitionTo(IngestionStatus.CHUNKING)).isTrue();
        assertThat(IngestionStatus.PARSING.canTransitionTo(IngestionStatus.FAILED)).isTrue();
        assertThat(IngestionStatus.CHUNKING.canTransitionTo(IngestionStatus.EMBEDDING)).isTrue();
        assertThat(IngestionStatus.CHUNKING.canTransitionTo(IngestionStatus.FAILED)).isTrue();
        assertThat(IngestionStatus.EMBEDDING.canTransitionTo(IngestionStatus.INDEXING)).isTrue();
        assertThat(IngestionStatus.EMBEDDING.canTransitionTo(IngestionStatus.FAILED)).isTrue();
        assertThat(IngestionStatus.INDEXING.canTransitionTo(IngestionStatus.INDEXED)).isTrue();
        assertThat(IngestionStatus.INDEXING.canTransitionTo(IngestionStatus.FAILED)).isTrue();
        assertThat(IngestionStatus.FAILED.canTransitionTo(IngestionStatus.PARSING)).isTrue();
    }

    @Test
    void rejectsUndeclaredAndTerminalTransitions() {
        for (IngestionStatus source : IngestionStatus.values()) {
            for (IngestionStatus target : IngestionStatus.values()) {
                boolean allowed = source.canTransitionTo(target);
                boolean declared = switch (source) {
                    case UPLOADED -> target == IngestionStatus.PARSING || target == IngestionStatus.FAILED;
                    case PARSING -> target == IngestionStatus.CHUNKING || target == IngestionStatus.FAILED;
                    case CHUNKING -> target == IngestionStatus.EMBEDDING || target == IngestionStatus.FAILED;
                    case EMBEDDING -> target == IngestionStatus.INDEXING || target == IngestionStatus.FAILED;
                    case INDEXING -> target == IngestionStatus.INDEXED || target == IngestionStatus.FAILED;
                    case FAILED -> target == IngestionStatus.PARSING;
                    case INDEXED -> false;
                };
                assertThat(allowed).isEqualTo(declared);
            }
        }
    }
}
