package com.lqq.supportflow;

import com.jayway.jsonpath.JsonPath;
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
import org.springframework.test.web.servlet.MvcResult;

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

    @Test
    void refreshRotatesTokenAndLogoutRevokesIt() throws Exception {
        String registration = """
                {"tenantCode":"refresh-shop","tenantName":"Refresh Shop","email":"admin@refresh.test","displayName":"Refresh Admin","password":"safe-password-123"}
                """;
        mockMvc.perform(post("/api/v1/tenants/register").contentType("application/json").content(registration))
                .andExpect(status().isCreated());
        String login = """
                {"tenantCode":"refresh-shop","email":"admin@refresh.test","password":"safe-password-123"}
                """;
        MvcResult loginResult = mockMvc.perform(post("/api/v1/auth/login").contentType("application/json").content(login))
                .andExpect(status().isOk())
                .andReturn();
        String originalRefresh = JsonPath.read(loginResult.getResponse().getContentAsString(), "$.refreshToken");

        MvcResult refreshResult = mockMvc.perform(post("/api/v1/auth/refresh")
                        .contentType("application/json")
                        .content("{\"refreshToken\":\"" + originalRefresh + "\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.refreshToken").isNotEmpty())
                .andReturn();
        String rotatedRefresh = JsonPath.read(refreshResult.getResponse().getContentAsString(), "$.refreshToken");
        mockMvc.perform(post("/api/v1/auth/refresh")
                        .contentType("application/json")
                        .content("{\"refreshToken\":\"" + originalRefresh + "\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("INVALID_CREDENTIALS"));

        mockMvc.perform(post("/api/v1/auth/logout")
                        .contentType("application/json")
                        .content("{\"refreshToken\":\"" + rotatedRefresh + "\"}"))
                .andExpect(status().isNoContent());
        mockMvc.perform(post("/api/v1/auth/refresh")
                        .contentType("application/json")
                        .content("{\"refreshToken\":\"" + rotatedRefresh + "\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void accessTokenAuthenticatesSessionEndpoint() throws Exception {
        String registration = """
                {"tenantCode":"session-shop","tenantName":"Session Shop","email":"admin@session.test","displayName":"Session Admin","password":"safe-password-123"}
                """;
        mockMvc.perform(post("/api/v1/tenants/register").contentType("application/json").content(registration))
                .andExpect(status().isCreated());
        String login = """
                {"tenantCode":"session-shop","email":"admin@session.test","password":"safe-password-123"}
                """;
        MvcResult loginResult = mockMvc.perform(post("/api/v1/auth/login").contentType("application/json").content(login))
                .andExpect(status().isOk())
                .andReturn();
        String accessToken = JsonPath.read(loginResult.getResponse().getContentAsString(), "$.accessToken");

        mockMvc.perform(get("/api/v1/auth/session"))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/auth/session").header("Authorization", "Bearer " + accessToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.role").value("TENANT_ADMIN"));
    }
}
