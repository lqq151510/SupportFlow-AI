package com.lqq.supportflow.shared.api;

import static org.assertj.core.api.Assertions.assertThat;

import com.lqq.supportflow.shared.LocalSecureStorageUnavailableException;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.mock.web.MockHttpServletRequest;

class GlobalExceptionHandlerTest {

    @Test
    void localSecureStorageProblemIsRecoverableAndDoesNotRevealConfigurationNames() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader(RequestIdFilter.REQUEST_ID_HEADER, "secure-storage-test");

        ProblemDetail problem = new GlobalExceptionHandler()
                .handleLocalSecureStorageUnavailable(new LocalSecureStorageUnavailableException(), request);

        assertThat(problem.getStatus()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE.value());
        assertThat(problem.getType()).hasToString("https://supportflow.dev/problems/local-secure-storage-unavailable");
        assertThat(problem.getDetail()).isEqualTo("local secure storage is unavailable");
        assertThat(problem.getProperties())
                .containsEntry("code", "LOCAL_SECURE_STORAGE_UNAVAILABLE")
                .containsEntry("requestId", "secure-storage-test");
        assertThat(problem.getDetail()).doesNotContain("MODEL_SECRET_MASTER_KEY");
    }
}
