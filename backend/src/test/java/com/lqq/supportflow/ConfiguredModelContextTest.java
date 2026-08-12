package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;

import com.lqq.supportflow.model.domain.ChatModelGateway;
import com.lqq.supportflow.model.infrastructure.protocol.ConfiguredChatModelGateway;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest(properties = "supportflow.model.mock.enabled=false")
class ConfiguredModelContextTest {

    @Autowired
    private ChatModelGateway gateway;

    @Test
    void realModelModeSelectsConfiguredGateway() {
        assertThat(gateway).isInstanceOf(ConfiguredChatModelGateway.class);
    }
}
