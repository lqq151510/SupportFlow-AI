package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.lqq.supportflow.model.infrastructure.security.ApiKeyCipher;
import com.lqq.supportflow.model.infrastructure.security.ModelBaseUrlValidator;
import org.junit.jupiter.api.Test;

class ModelSecurityTest {
    private static final String MASTER_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=";

    @Test void encryptsWithRandomNonceAndDecrypts() {
        ApiKeyCipher cipher = new ApiKeyCipher();
        String encrypted = cipher.encrypt("sk-secret", MASTER_KEY);
        assertThat(encrypted).isNotEqualTo("sk-secret");
        assertThat(cipher.decrypt(encrypted, MASTER_KEY)).isEqualTo("sk-secret");
    }

    @Test void rejectsNonPublicModelUrls() {
        ModelBaseUrlValidator validator = new ModelBaseUrlValidator();
        validator.validate("https://api.example.com/v1");
        assertThatThrownBy(() -> validator.validate("http://api.example.com")).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> validator.validate("https://127.0.0.1/v1")).isInstanceOf(IllegalArgumentException.class);
    }

    @Test void rejectsInvalidCiphertextAndMasterKeyMaterial() {
        ApiKeyCipher cipher = new ApiKeyCipher();

        assertThatThrownBy(() -> cipher.encrypt("sk-secret", "not-base64"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("cannot encrypt model API key");
        assertThatThrownBy(() -> cipher.decrypt("not-base64", MASTER_KEY))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("cannot decrypt model API key");
        assertThatThrownBy(() -> cipher.encrypt("sk-secret", "MTIz"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("cannot encrypt model API key");
    }
}
