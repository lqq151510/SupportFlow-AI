package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import com.jayway.jsonpath.JsonPath;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
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
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.jdbc.core.JdbcTemplate;

@SpringBootTest
@AutoConfigureMockMvc
class SupportFlowApplicationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbc;


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
    void viteDevelopmentOriginCanPreflightAuthenticatedRequests() throws Exception {
        mockMvc.perform(options("/api/v1/admin/approvals")
                        .header("Origin", "http://localhost:5173")
                        .header("Access-Control-Request-Method", "POST")
                        .header("Access-Control-Request-Headers", "authorization,idempotency-key"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "http://localhost:5173"))
                .andExpect(header().string("Access-Control-Allow-Methods", org.hamcrest.Matchers.containsString("POST")))
                .andExpect(header().string("Access-Control-Allow-Headers", org.hamcrest.Matchers.containsString("idempotency-key")));
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

    @Test
    void tenantAdminManagesOnlyItsActiveMembers() throws Exception {
        String registration = """
                {"tenantCode":"admin-shop","tenantName":"Admin Shop","email":"admin@members.test","displayName":"Admin","password":"safe-password-123"}
                """;
        mockMvc.perform(post("/api/v1/tenants/register").contentType("application/json").content(registration))
                .andExpect(status().isCreated());
        String adminToken = loginAccessToken("admin-shop", "admin@members.test", "safe-password-123");

        String member = """
                {"email":"agent@members.test","displayName":"Support Agent","password":"safe-password-456","role":"AGENT"}
                """;
        MvcResult memberResult = mockMvc.perform(post("/api/v1/admin/members")
                        .header("Authorization", "Bearer " + adminToken)
                        .contentType("application/json")
                        .content(member))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.userId").isNumber())
                .andExpect(jsonPath("$.membershipId").isNumber())
                .andReturn();
        Number membershipId = JsonPath.read(memberResult.getResponse().getContentAsString(), "$.membershipId");
        mockMvc.perform(post("/api/v1/auth/login").contentType("application/json")
                        .content("{\"tenantCode\":\"admin-shop\",\"email\":\"agent@members.test\",\"password\":\"safe-password-456\"}"))
                .andExpect(status().isOk());

        mockMvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch(
                        "/api/v1/admin/members/" + membershipId.longValue() + "/status")
                        .header("Authorization", "Bearer " + adminToken)
                        .contentType("application/json")
                        .content("{\"status\":\"DISABLED\"}"))
                .andExpect(status().isNoContent());
        mockMvc.perform(post("/api/v1/auth/login").contentType("application/json")
                        .content("{\"tenantCode\":\"admin-shop\",\"email\":\"agent@members.test\",\"password\":\"safe-password-456\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void passwordChangeRevokesRefreshTokensAndRequiresNewPassword() throws Exception {
        String registration = """
                {"tenantCode":"password-shop","tenantName":"Password Shop","email":"admin@password.test","displayName":"Admin","password":"safe-password-123"}
                """;
        mockMvc.perform(post("/api/v1/tenants/register").contentType("application/json").content(registration))
                .andExpect(status().isCreated());
        MvcResult loginResult = mockMvc.perform(post("/api/v1/auth/login").contentType("application/json")
                        .content("{\"tenantCode\":\"password-shop\",\"email\":\"admin@password.test\",\"password\":\"safe-password-123\"}"))
                .andExpect(status().isOk())
                .andReturn();
        String accessToken = JsonPath.read(loginResult.getResponse().getContentAsString(), "$.accessToken");
        String refreshToken = JsonPath.read(loginResult.getResponse().getContentAsString(), "$.refreshToken");

        mockMvc.perform(post("/api/v1/auth/change-password")
                        .header("Authorization", "Bearer " + accessToken)
                        .contentType("application/json")
                        .content("{\"currentPassword\":\"safe-password-123\",\"newPassword\":\"safe-password-789\"}"))
                .andExpect(status().isNoContent());
        mockMvc.perform(post("/api/v1/auth/refresh").contentType("application/json")
                        .content("{\"refreshToken\":\"" + refreshToken + "\"}"))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(post("/api/v1/auth/login").contentType("application/json")
                        .content("{\"tenantCode\":\"password-shop\",\"email\":\"admin@password.test\",\"password\":\"safe-password-123\"}"))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(post("/api/v1/auth/login").contentType("application/json")
                        .content("{\"tenantCode\":\"password-shop\",\"email\":\"admin@password.test\",\"password\":\"safe-password-789\"}"))
                .andExpect(status().isOk());
    }

    @Test
    void customerOrdersAreScopedByAuthenticatedTenantAndCustomer() throws Exception {
        registerTenant("order-shop-a", "admin@orders-a.test");
        registerTenant("order-shop-b", "admin@orders-b.test");
        registerCustomer("order-shop-a", "customer@orders-a.test");
        registerCustomer("order-shop-b", "customer@orders-b.test");

        String customerAToken = loginAccessToken("order-shop-a", "customer@orders-a.test", "safe-password-123");
        String customerBToken = loginAccessToken("order-shop-b", "customer@orders-b.test", "safe-password-123");
        mockMvc.perform(get("/api/v1/customer/orders/DEMO-001").header("Authorization", "Bearer " + customerAToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("PAID"));
        mockMvc.perform(get("/api/v1/customer/orders/DEMO-001").header("Authorization", "Bearer " + customerBToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("PAID"));
        mockMvc.perform(get("/api/v1/customer/orders/DEMO-001/shipment").header("Authorization", "Bearer " + customerAToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.trackingNo").value("SF-DEMO-001"));
        mockMvc.perform(get("/api/v1/customer/orders/DEMO-001/refund-eligibility").header("Authorization", "Bearer " + customerAToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.eligible").value(true));
    }

    @Test
    void knowledgeDocumentRegistrationIsDeduplicatedAndTenantScoped() throws Exception {
        registerTenant("knowledge-owner", "admin@knowledge-owner.test");
        registerTenant("knowledge-attacker", "admin@knowledge-attacker.test");
        String ownerToken = loginAccessToken("knowledge-owner", "admin@knowledge-owner.test", "safe-password-123");
        String attackerToken = loginAccessToken("knowledge-attacker", "admin@knowledge-attacker.test", "safe-password-123");
        MvcResult base = mockMvc.perform(post("/api/v1/admin/knowledge-bases")
                        .header("Authorization", "Bearer " + ownerToken).contentType("application/json")
                        .content("{\"name\":\"Policies\",\"description\":\"Support policies\"}"))
                .andExpect(status().isCreated()).andReturn();
        String knowledgeBaseId = JsonPath.read(base.getResponse().getContentAsString(), "$.id");
        String path = "/api/v1/admin/knowledge-bases/" + knowledgeBaseId + "/documents";
        String document = "{\"fileName\":\"policy.txt\",\"content\":\"Refund policy content\"}";
        MvcResult uploaded = mockMvc.perform(post(path).header("Authorization", "Bearer " + ownerToken).contentType("application/json").content(document))
                .andExpect(status().isCreated()).andExpect(jsonPath("$.status").value("EMBEDDING")).andReturn();
        String documentId = JsonPath.read(uploaded.getResponse().getContentAsString(), "$.id");
        mockMvc.perform(get("/api/v1/admin/knowledge-bases").header("Authorization", "Bearer " + ownerToken))
                .andExpect(status().isOk()).andExpect(jsonPath("$[0].id").value(knowledgeBaseId))
                .andExpect(jsonPath("$[0].name").value("Policies"));
        mockMvc.perform(get(path).header("Authorization", "Bearer " + ownerToken))
                .andExpect(status().isOk()).andExpect(jsonPath("$[0].id").value(documentId))
                .andExpect(jsonPath("$[0].fileName").value("policy.txt"));
        mockMvc.perform(get("/api/v1/admin/knowledge-bases").header("Authorization", "Bearer " + attackerToken))
                .andExpect(status().isOk()).andExpect(jsonPath("$").isEmpty());
        mockMvc.perform(get(path).header("Authorization", "Bearer " + attackerToken))
                .andExpect(status().isBadRequest());
        mockMvc.perform(get(path + "/" + documentId).header("Authorization", "Bearer " + ownerToken))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("EMBEDDING")).andExpect(jsonPath("$.chunkCount").value(1));
        mockMvc.perform(post(path).header("Authorization", "Bearer " + ownerToken).contentType("application/json").content(document))
                .andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("RESOURCE_CONFLICT"));
        mockMvc.perform(post(path).header("Authorization", "Bearer " + attackerToken).contentType("application/json")
                        .content("{\"fileName\":\"attack.txt\",\"content\":\"Other content\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void modelConfigurationCatalogIsTenantScopedAndNeverReturnsSecrets() throws Exception {
        registerTenant("model-owner", "admin@model-owner.test");
        registerTenant("model-other", "admin@model-other.test");
        String ownerToken = loginAccessToken("model-owner", "admin@model-owner.test", "safe-password-123");
        String otherToken = loginAccessToken("model-other", "admin@model-other.test", "safe-password-123");

        Long tenantId = jdbc.queryForObject("SELECT id FROM tenants WHERE code = ?", Long.class, "model-owner");
        long modelId = 9_007_199_254_740_993L;
        jdbc.update("INSERT INTO model_configs (id, tenant_id, name, protocol, base_url, model_name, encrypted_api_key, is_default, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                modelId, tenantId, "Primary chat", "OPENAI_COMPATIBLE", "https://api.example.com/v1", "support-model", "encrypted-test-fixture", true);

        mockMvc.perform(get("/api/v1/admin/models").header("Authorization", "Bearer " + ownerToken))
                .andExpect(status().isOk()).andExpect(jsonPath("$[0].id").value(Long.toString(modelId)))
                .andExpect(jsonPath("$[0].modelName").value("support-model"))
                .andExpect(jsonPath("$[0].apiKey").doesNotExist());
        mockMvc.perform(get("/api/v1/admin/models").header("Authorization", "Bearer " + otherToken))
                .andExpect(status().isOk()).andExpect(jsonPath("$").isEmpty());
    }

    @Test
    void knowledgeDocumentUploadStoresAndExtractsTextBeforeChunking() throws Exception {
        registerTenant("knowledge-upload", "admin@knowledge-upload.test");
        String token = loginAccessToken("knowledge-upload", "admin@knowledge-upload.test", "safe-password-123");
        MvcResult base = mockMvc.perform(post("/api/v1/admin/knowledge-bases")
                        .header("Authorization", "Bearer " + token).contentType("application/json")
                        .content("{\"name\":\"Returns\",\"description\":\"Return policy\"}"))
                .andExpect(status().isCreated()).andReturn();
        String knowledgeBaseId = JsonPath.read(base.getResponse().getContentAsString(), "$.id");
        String path = "/api/v1/admin/knowledge-bases/" + knowledgeBaseId + "/documents/upload";
        MockMultipartFile file = new MockMultipartFile("file", "returns.md", "text/markdown", "# Returns\nItems can be returned within 30 days.".getBytes());
        mockMvc.perform(multipart(path).file(file).header("Authorization", "Bearer " + token))
                .andExpect(status().isCreated()).andExpect(jsonPath("$.status").value("EMBEDDING"));
        mockMvc.perform(multipart(path).file(file).header("Authorization", "Bearer " + token))
                .andExpect(status().isConflict());
    }

    @Test
    void customerMessageSubmissionIsTenantScopedAndIdempotent() throws Exception {
        registerTenant("conversation-shop", "admin@conversation.test");
        registerCustomer("conversation-shop", "customer@conversation.test");
        String token = loginAccessToken("conversation-shop", "customer@conversation.test", "safe-password-123");
        MvcResult created = mockMvc.perform(post("/api/v1/customer/conversations").header("Authorization", "Bearer " + token))
                .andExpect(status().isCreated()).andReturn();
        String conversationId = JsonPath.read(created.getResponse().getContentAsString(), "$.id");
        String path = "/api/v1/customer/conversations/" + conversationId + "/messages";
        MvcResult first = mockMvc.perform(post(path).header("Authorization", "Bearer " + token).header("Idempotency-Key", "message-1")
                        .contentType("application/json").content("{\"content\":\"Where is my order?\"}"))
                .andExpect(status().isAccepted()).andExpect(jsonPath("$.status").value("QUEUED")).andReturn();
        String generationId = JsonPath.read(first.getResponse().getContentAsString(), "$.id");
        mockMvc.perform(post(path).header("Authorization", "Bearer " + token).header("Idempotency-Key", "message-1")
                        .contentType("application/json").content("{\"content\":\"Where is my order?\"}"))
                .andExpect(status().isAccepted()).andExpect(jsonPath("$.id").value(generationId));
        mockMvc.perform(post(path).header("Authorization", "Bearer " + token).header("Idempotency-Key", "message-2")
                        .contentType("application/json").content("{\"content\":\"我要人工客服处理退款\"}"))
                .andExpect(status().isAccepted()).andExpect(jsonPath("$.status").value("HANDOFF_REQUIRED"));
    }

    @Test
    void approvedActionIsRecordedOnceAndDispatchedOnceAfterDecisionReplay() throws Exception {
        registerTenant("approval-shop", "admin@approval.test");
        String token = loginAccessToken("approval-shop", "admin@approval.test", "safe-password-123");

        MvcResult created = mockMvc.perform(post("/api/v1/admin/approvals")
                        .header("Authorization", "Bearer " + token)
                        .contentType("application/json")
                        .content("""
                                {"actionType":"refund.request","actionSummary":"Refund eligible order",
                                 "orderNo":"DEMO-001","amount":88.00,"currency":"CNY",
                                 "eligibilityEvidence":"eligible=true; reason=within refund window"}
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("PENDING"))
                .andExpect(jsonPath("$.orderNo").value("DEMO-001"))
                .andExpect(jsonPath("$.amount").value(88.00))
                .andExpect(jsonPath("$.currency").value("CNY"))
                .andExpect(jsonPath("$.version").value(0))
                .andReturn();
        String approvalId = JsonPath.read(created.getResponse().getContentAsString(), "$.id");
        String decisionPath = "/api/v1/admin/approvals/" + approvalId + "/decision";

        for (int attempt = 0; attempt < 2; attempt++) {
            mockMvc.perform(post(decisionPath)
                            .header("Authorization", "Bearer " + token)
                            .header("Idempotency-Key", "approve-refund-1")
                            .contentType("application/json")
                            .content("{\"decision\":\"APPROVED\"}"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.status").value("APPROVED"))
                    .andExpect(jsonPath("$.version").value(1));
        }
        mockMvc.perform(post(decisionPath)
                        .header("Authorization", "Bearer " + token)
                        .header("Idempotency-Key", "approve-refund-1")
                        .contentType("application/json")
                        .content("{\"decision\":\"REJECTED\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("RESOURCE_CONFLICT"));

        mockMvc.perform(post("/api/v1/admin/outbox/dispatch")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.published").value(1));
        assertThat(jdbc.queryForObject("""
                SELECT COUNT(*) FROM action_executions
                WHERE approval_id = ? AND execution_version = 1
                  AND business_idempotency_key = ? AND status = 'EXECUTED'
                """, Integer.class, Long.valueOf(approvalId),
                "approval:" + approvalId + ":v1:execution:1")).isEqualTo(1);
        mockMvc.perform(post("/api/v1/admin/outbox/dispatch")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.published").value(1));
        mockMvc.perform(post("/api/v1/admin/outbox/dispatch")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.published").value(0));
    }

    @Test
    void pendingApprovalCanBeRevokedIdempotently() throws Exception {
        registerTenant("revoke-shop", "admin@revoke.test");
        String token = loginAccessToken("revoke-shop", "admin@revoke.test", "safe-password-123");
        MvcResult created = mockMvc.perform(post("/api/v1/admin/approvals")
                        .header("Authorization", "Bearer " + token)
                        .contentType("application/json")
                        .content("""
                                {"actionType":"compensation.issue","actionSummary":"Service recovery credit",
                                 "orderNo":"DEMO-001","amount":20.00,"currency":"CNY",
                                 "eligibilityEvidence":"agent verified service interruption"}
                                """))
                .andExpect(status().isCreated()).andReturn();
        String approvalId = JsonPath.read(created.getResponse().getContentAsString(), "$.id");
        for (int attempt = 0; attempt < 2; attempt++) {
            mockMvc.perform(post("/api/v1/admin/approvals/" + approvalId + "/revoke")
                            .header("Authorization", "Bearer " + token)
                            .header("Idempotency-Key", "revoke-compensation-1"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.status").value("REVOKED"))
                    .andExpect(jsonPath("$.version").value(1));
        }
    }

    @Test
    void handoffCreatesTicketThatAnAgentCanClaimCommentResolveAndClose() throws Exception {
        registerTenant("ticket-shop", "admin@ticket.test");
        registerCustomer("ticket-shop", "customer@ticket.test");
        String customerToken = loginAccessToken("ticket-shop", "customer@ticket.test", "safe-password-123");
        String adminToken = loginAccessToken("ticket-shop", "admin@ticket.test", "safe-password-123");
        MvcResult conversation = mockMvc.perform(post("/api/v1/customer/conversations")
                        .header("Authorization", "Bearer " + customerToken))
                .andExpect(status().isCreated())
                .andReturn();
        String conversationId = JsonPath.read(conversation.getResponse().getContentAsString(), "$.id");
        mockMvc.perform(post("/api/v1/customer/conversations/" + conversationId + "/messages")
                        .header("Authorization", "Bearer " + customerToken)
                        .header("Idempotency-Key", "ticket-handoff-1")
                        .contentType("application/json")
                        .content("{\"content\":\"我要人工客服处理退款\"}"))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.status").value("HANDOFF_REQUIRED"));

        MvcResult tickets = mockMvc.perform(get("/api/v1/admin/tickets")
                        .header("Authorization", "Bearer " + adminToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].status").value("NEW"))
                .andExpect(jsonPath("$[0].priority").value("NORMAL"))
                .andReturn();
        String ticketId = JsonPath.read(tickets.getResponse().getContentAsString(), "$[0].id");
        String ticketPath = "/api/v1/admin/tickets/" + ticketId;
        mockMvc.perform(post(ticketPath + "/claim").header("Authorization", "Bearer " + adminToken))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("OPEN"));
        mockMvc.perform(post(ticketPath + "/comments").header("Authorization", "Bearer " + adminToken)
                        .contentType("application/json").content("{\"content\":\"正在为您核实退款资格\"}"))
                .andExpect(status().isCreated());
        mockMvc.perform(post(ticketPath + "/status").header("Authorization", "Bearer " + adminToken)
                        .contentType("application/json").content("{\"status\":\"RESOLVED\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("RESOLVED"));
        mockMvc.perform(post(ticketPath + "/status").header("Authorization", "Bearer " + adminToken)
                        .contentType("application/json").content("{\"status\":\"CLOSED\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("CLOSED"));
    }

    private void registerTenant(String tenantCode, String email) throws Exception {
        String body = "{\"tenantCode\":\"" + tenantCode + "\",\"tenantName\":\"" + tenantCode
                + "\",\"email\":\"" + email + "\",\"displayName\":\"Admin\",\"password\":\"safe-password-123\"}";
        mockMvc.perform(post("/api/v1/tenants/register").contentType("application/json").content(body))
                .andExpect(status().isCreated());
    }

    private void registerCustomer(String tenantCode, String email) throws Exception {
        String body = "{\"tenantCode\":\"" + tenantCode + "\",\"email\":\"" + email
                + "\",\"displayName\":\"Customer\",\"password\":\"safe-password-123\"}";
        mockMvc.perform(post("/api/v1/customers/register").contentType("application/json").content(body))
                .andExpect(status().isCreated())
                .andReturn();
    }

    private String loginAccessToken(String tenantCode, String email, String password) throws Exception {
        MvcResult result = mockMvc.perform(post("/api/v1/auth/login").contentType("application/json")
                        .content("{\"tenantCode\":\"" + tenantCode + "\",\"email\":\"" + email + "\",\"password\":\"" + password + "\"}"))
                .andExpect(status().isOk())
                .andReturn();
        return JsonPath.read(result.getResponse().getContentAsString(), "$.accessToken");
    }
}
