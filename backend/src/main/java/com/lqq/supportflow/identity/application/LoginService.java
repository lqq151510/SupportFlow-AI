package com.lqq.supportflow.identity.application;

import com.lqq.supportflow.identity.domain.AuthenticationPort;
import com.lqq.supportflow.identity.domain.RefreshTokenPort;
import com.lqq.supportflow.identity.domain.TokenIssuer;
import java.time.Instant;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class LoginService {
    private final AuthenticationPort port;
    private final PasswordEncoder encoder;
    private final TokenIssuer tokens;
    private final RefreshTokenPort refreshTokens;

    public LoginService(AuthenticationPort port, PasswordEncoder encoder, TokenIssuer tokens, RefreshTokenPort refreshTokens) {
        this.port = port;
        this.encoder = encoder;
        this.tokens = tokens;
        this.refreshTokens = refreshTokens;
    }

    public TokenPair login(String tenantCode, String email, String password) {
        var principal = port.findActivePrincipal(tenantCode, email)
                .filter(value -> encoder.matches(password, value.passwordHash()))
                .orElseThrow(() -> new BadCredentialsException("invalid credentials"));
        var refreshToken = tokens.issueRefreshToken(
                principal.userId(), principal.tenantId(), principal.membershipId(), principal.role());
        refreshTokens.save(
                principal.userId(), principal.tenantId(), refreshToken.jti(), refreshToken.value(), refreshToken.expiresAt());
        var accessToken = tokens.issueAccessToken(
                principal.userId(), principal.tenantId(), principal.membershipId(), principal.role());
        return new TokenPair(accessToken.value(), refreshToken.value());
    }

    public record TokenPair(String accessToken, String refreshToken) { }
}
