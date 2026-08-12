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

    @Test void identifiesEveryExplicitHumanHandoffSignalWithoutCaseSensitivity() {
        com.lqq.supportflow.conversation.domain.HandoffPolicy policy = new com.lqq.supportflow.conversation.domain.HandoffPolicy();

        for (String signal : java.util.List.of("人工客服", "HUMAN agent", "投诉", "威胁", "refund request", "我要退款", "compensation", "申请补偿")) {
            assertThat(policy.requiresHandoff(signal)).isTrue();
        }
        assertThat(policy.requiresHandoff("请查询订单物流")).isFalse();
    }

    @Test void rejectsInvalidCiphertextAndMasterKeyMaterial() {
        ApiKeyCipher cipher = new ApiKeyCipher();
        String differentKey = "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXowMTIzNDU2Nzg5";

        assertThatThrownBy(() -> cipher.encrypt("sk-secret", "not-base64"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("cannot encrypt model API key");
        assertThatThrownBy(() -> cipher.decrypt("not-base64", MASTER_KEY))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("cannot decrypt model API key");
        assertThatThrownBy(() -> cipher.encrypt("sk-secret", "MTIz"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("cannot encrypt model API key");
        assertThatThrownBy(() -> cipher.decrypt(cipher.encrypt("sk-secret", MASTER_KEY), differentKey))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("cannot decrypt model API key");
        assertThatThrownBy(() -> cipher.decrypt("AA==", "MTIz"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("cannot decrypt model API key");
    }
}
