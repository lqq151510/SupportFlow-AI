package com.lqq.supportflow.conversation.domain;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

class ConversationJsonSerializationTest {

    private final ObjectMapper json = new ObjectMapper();

    @Test
    void serializesSnowflakeIdentifiersAsStringsForJavascriptClients() throws Exception {
        long snowflakeId = 2_086_355_280_098_861_057L;

        String payload = json.writeValueAsString(new Conversation(snowflakeId, ConversationStatus.AI_ACTIVE));

        assertThat(payload).contains("\"id\":\"2086355280098861057\"");
    }
}
