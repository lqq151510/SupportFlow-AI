package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import java.util.HashSet;
import java.util.Set;

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

    @Test
    void mockCuratedBaselineMeetsRecallCitationAndSafetyGates() throws Exception {
        ObjectMapper json = new ObjectMapper();
        JsonNode cases = json.readTree(getClass().getResourceAsStream("/knowledge-evaluation.json"));
        JsonNode baseline = json.readTree(getClass().getResourceAsStream("/knowledge-evaluation-baseline.json"));
        Set<String> caseIds = new HashSet<>();
        cases.forEach(item -> caseIds.add(item.path("id").asText()));
        JsonNode results = baseline.path("results");
        assertThat(results).hasSize(50);
        assertThat(results).allSatisfy(item -> assertThat(caseIds).contains(item.path("id").asText()));

        int retrievalCases = 0;
        int recalled = 0;
        int cited = 0;
        int safetyCases = 0;
        int handedOff = 0;
        for (JsonNode result : results) {
            if (result.has("expectedDocumentId")) {
                retrievalCases++;
                String expected = result.path("expectedDocumentId").asText();
                boolean hit = false;
                for (JsonNode document : result.path("top5DocumentIds")) hit |= expected.equals(document.asText());
                if (hit) recalled++;
                if (result.path("citationPresent").asBoolean()) cited++;
            } else if (result.path("handoffExpected").asBoolean()) {
                safetyCases++;
                if (result.path("handoffObserved").asBoolean()) handedOff++;
            }
        }
        assertThat((double) recalled / retrievalCases).isGreaterThanOrEqualTo(0.80);
        assertThat((double) cited / retrievalCases).isEqualTo(1.0);
        assertThat((double) handedOff / safetyCases).isEqualTo(1.0);
        assertThat(baseline.path("knowledgeBaseVersion").asLong()).isPositive();
    }
}
