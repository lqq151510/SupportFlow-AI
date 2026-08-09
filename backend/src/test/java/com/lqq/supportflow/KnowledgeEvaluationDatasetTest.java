package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

class KnowledgeEvaluationDatasetTest {
    @Test
    void containsFiftyWellFormedEcommerceSupportCases() throws Exception {
        JsonNode cases = new ObjectMapper().readTree(getClass().getResourceAsStream("/knowledge-evaluation.json"));
        assertThat(cases).hasSize(50);
        for (JsonNode item : cases) {
            assertThat(item.path("id").asText()).isNotBlank();
            assertThat(item.path("category").asText()).isNotBlank();
            assertThat(item.path("query").asText()).isNotBlank();
            assertThat(item.path("expectedTerms")).isNotEmpty();
        }
    }
}
