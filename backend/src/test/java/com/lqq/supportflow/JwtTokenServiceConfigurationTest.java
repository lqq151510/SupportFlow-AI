package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThatIllegalStateException;

import com.lqq.supportflow.identity.infrastructure.security.JwtProperties;
import com.lqq.supportflow.identity.infrastructure.security.JwtTokenService;
import java.time.Duration;
import org.junit.jupiter.api.Test;

class JwtTokenServiceConfigurationTest {

    @Test
    void failsFastWhenTheDockerJwtSecretIsMissingOrUnsafe() {
        assertThatIllegalStateException()
                .isThrownBy(() -> service(""))
                .withMessageContaining("SUPPORTFLOW_JWT_SECRET_BASE64 must be set");
        assertThatIllegalStateException()
                .isThrownBy(() -> service("not-base64"))
                .withMessageContaining("must be valid Base64");
        assertThatIllegalStateException()
                .isThrownBy(() -> service("c2hvcnQ="))
                .withMessageContaining("must decode to at least 32 bytes");
    }

    private JwtTokenService service(String secretBase64) {
        return new JwtTokenService(new JwtProperties(secretBase64, Duration.ofMinutes(15), Duration.ofDays(7)));
    }
}
