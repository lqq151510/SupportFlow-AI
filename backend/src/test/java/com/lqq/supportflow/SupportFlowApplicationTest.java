package com.lqq.supportflow;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.modulith.core.ApplicationModules;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class SupportFlowApplicationTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void applicationModulesRespectBoundaries() {
        ApplicationModules.of(SupportFlowApplication.class).verify();
    }

    @Test
    void healthEndpointIsPublicAndIncludesRequestId() throws Exception {
        mockMvc.perform(get("/actuator/health").header("X-Request-Id", "health-check-1"))
                .andExpect(status().isOk())
                .andExpect(header().string("X-Request-Id", "health-check-1"));
    }
}
