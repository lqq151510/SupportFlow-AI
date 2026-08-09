package com.lqq.supportflow;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
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

    @Test
    void tenantRegistrationCreatesAdminAndRejectsDuplicateTenantCode() throws Exception {
        String body = """
                {"tenantCode":"acme-shop","tenantName":"Acme Shop","email":"admin@acme.test","displayName":"Acme Admin","password":"safe-password-123"}
                """;
        mockMvc.perform(post("/api/v1/tenants/register").contentType("application/json").content(body))
                .andExpect(status().isCreated()).andExpect(jsonPath("$.tenantId").isString())
                .andExpect(jsonPath("$.userId").isString()).andExpect(jsonPath("$.membershipId").isString());
        mockMvc.perform(post("/api/v1/tenants/register").contentType("application/json").content(body))
                .andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("RESOURCE_CONFLICT"));
    }

    @Test
    void customerRegistrationRequiresExistingTenantAndCreatesCustomerMembership() throws Exception {
        String tenant = "{\"tenantCode\":\"buyer-shop\",\"tenantName\":\"Buyer Shop\",\"email\":\"owner@buyer.test\",\"displayName\":\"Owner\",\"password\":\"safe-password-123\"}";
        mockMvc.perform(post("/api/v1/tenants/register").contentType("application/json").content(tenant)).andExpect(status().isCreated());
        String customer = "{\"tenantCode\":\"buyer-shop\",\"email\":\"buyer@buyer.test\",\"displayName\":\"Buyer\",\"password\":\"safe-password-123\"}";
        mockMvc.perform(post("/api/v1/customers/register").contentType("application/json").content(customer))
                .andExpect(status().isCreated()).andExpect(jsonPath("$.tenantId").isString()).andExpect(jsonPath("$.membershipId").isString());
        mockMvc.perform(post("/api/v1/customers/register").contentType("application/json").content(customer))
                .andExpect(status().isConflict());
    }

    @Test
    void loginIssuesTokenPairAndRejectsInvalidCredentials() throws Exception {
        String registration = """
                {"tenantCode":"login-shop","tenantName":"Login Shop","email":"admin@login.test","displayName":"Login Admin","password":"safe-password-123"}
                """;
        mockMvc.perform(post("/api/v1/tenants/register").contentType("application/json").content(registration))
                .andExpect(status().isCreated());

        String login = """
                {"tenantCode":"login-shop","email":"admin@login.test","password":"safe-password-123"}
                """;
        mockMvc.perform(post("/api/v1/auth/login").contentType("application/json").content(login))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.accessToken").isNotEmpty())
                .andExpect(jsonPath("$.refreshToken").isNotEmpty());

        String invalidLogin = """
                {"tenantCode":"login-shop","email":"admin@login.test","password":"wrong-password"}
                """;
        mockMvc.perform(post("/api/v1/auth/login").contentType("application/json").content(invalidLogin))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("INVALID_CREDENTIALS"));
    }
}
