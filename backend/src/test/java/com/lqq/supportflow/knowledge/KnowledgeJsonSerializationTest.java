package com.lqq.supportflow.knowledge;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.knowledge.domain.IngestionStatus;
import com.lqq.supportflow.knowledge.domain.KnowledgeBase;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocument;
import org.junit.jupiter.api.Test;

class KnowledgeJsonSerializationTest {

    private final ObjectMapper json = new ObjectMapper();

    @Test
    void serializesKnowledgeSnowflakeIdentifiersAsStringsForJavascriptClients() throws Exception {
        long snowflakeId = 2_086_355_280_098_861_057L;

        assertThat(json.writeValueAsString(new KnowledgeBase(snowflakeId, "Returns", "Policy", "ACTIVE", 1L)))
                .contains("\"id\":\"2086355280098861057\"");
        assertThat(json.writeValueAsString(new KnowledgeDocument(snowflakeId, "returns.md", "hash", IngestionStatus.INDEXED)))
                .contains("\"id\":\"2086355280098861057\"");
    }
}
