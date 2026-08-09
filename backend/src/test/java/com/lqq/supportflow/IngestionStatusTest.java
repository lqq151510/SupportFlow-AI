package com.lqq.supportflow;
import static org.assertj.core.api.Assertions.assertThat;
import com.lqq.supportflow.knowledge.domain.IngestionStatus; import org.junit.jupiter.api.Test;
class IngestionStatusTest { @Test void onlyAllowsForwardTransitionsOrRetry(){assertThat(IngestionStatus.UPLOADED.canTransitionTo(IngestionStatus.PARSING)).isTrue();assertThat(IngestionStatus.INDEXING.canTransitionTo(IngestionStatus.INDEXED)).isTrue();assertThat(IngestionStatus.FAILED.canTransitionTo(IngestionStatus.PARSING)).isTrue();assertThat(IngestionStatus.INDEXED.canTransitionTo(IngestionStatus.PARSING)).isFalse();}}
