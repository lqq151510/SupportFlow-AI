package com.lqq.supportflow.model.infrastructure.security;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.assertThat;

import com.lqq.supportflow.shared.LocalSecureStorageUnavailableException;
import org.junit.jupiter.api.Test;

class ApiKeyCipherTest {

    private static final String MASTER_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=";

    @Test
    void missingRuntimeMasterKeyDoesNotExposeTheEnvironmentVariableName() {
        ApiKeyCipher cipher = new ApiKeyCipher(() -> null);

        assertThatThrownBy(() -> cipher.encrypt("sk-test"))
                .isInstanceOf(LocalSecureStorageUnavailableException.class)
                .hasMessage("local secure storage is unavailable")
                .hasMessageNotContaining("MODEL_SECRET_MASTER_KEY");
    }

    @Test
    void blankRuntimeMasterKeyIsReportedWithoutLeakingItsSource() {
        ApiKeyCipher cipher = new ApiKeyCipher(() -> " ");

        assertThatThrownBy(() -> cipher.decrypt("ciphertext"))
                .isInstanceOf(LocalSecureStorageUnavailableException.class)
                .hasMessage("local secure storage is unavailable");
    }

    @Test
    void encryptsAndDecryptsWithTheInjectedRuntimeMasterKey() {
        ApiKeyCipher cipher = new ApiKeyCipher(() -> MASTER_KEY);

        assertThat(cipher.decrypt(cipher.encrypt("sk-test"))).isEqualTo("sk-test");
    }
}
