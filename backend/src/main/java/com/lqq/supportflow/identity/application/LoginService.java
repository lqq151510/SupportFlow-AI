package com.lqq.supportflow.identity.application;

import com.lqq.supportflow.identity.domain.AuthenticationPort;
import com.lqq.supportflow.identity.domain.RefreshTokenPort;
import com.lqq.supportflow.identity.domain.RefreshTokenVerifier;
import com.lqq.supportflow.identity.domain.TokenIssuer;
import java.time.Instant;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class LoginService {
    private final AuthenticationPort port;
    private final PasswordEncoder encoder;
    private final TokenIssuer tokens;
    private final RefreshTokenPort refreshTokens;
    private final RefreshTokenVerifier refreshTokenVerifier;

    public LoginService(
            AuthenticationPort port,
            PasswordEncoder encoder,
            TokenIssuer tokens,
            RefreshTokenPort refreshTokens,
            RefreshTokenVerifier refreshTokenVerifier) {
        this.port = port;
        this.encoder = encoder;
        this.tokens = tokens;
        this.refreshTokens = refreshTokens;
        this.refreshTokenVerifier = refreshTokenVerifier;
    }

    @Transactional
    public TokenPair login(String tenantCode, String email, String password) {
        var principal = port.findActivePrincipal(tenantCode, email)
                .filter(value -> encoder.matches(password, value.passwordHash()))
                .orElseThrow(() -> new BadCredentialsException("invalid credentials"));
        return issueTokenPair(principal.userId(), principal.tenantId(), principal.membershipId(), principal.role());
    }

    @Transactional
    public TokenPair refresh(String rawToken) {
        var subject = refreshTokenVerifier.verify(rawToken)
                .filter(value -> refreshTokens.isActive(
                        value.userId(), value.tenantId(), value.jti(), rawToken, Instant.now()))
                .orElseThrow(() -> new BadCredentialsException("invalid refresh token"));
        refreshTokens.revoke(subject.jti(), Instant.now());
        return issueTokenPair(subject.userId(), subject.tenantId(), subject.membershipId(), subject.role());
    }

    @Transactional
    public void logout(String rawToken) {
        refreshTokenVerifier.verify(rawToken)
                .filter(value -> refreshTokens.isActive(
                        value.userId(), value.tenantId(), value.jti(), rawToken, Instant.now()))
                .ifPresent(value -> refreshTokens.revoke(value.jti(), Instant.now()));
    }

    private TokenPair issueTokenPair(Long userId, Long tenantId, Long membershipId, String role) {
        var refreshToken = tokens.issueRefreshToken(userId, tenantId, membershipId, role);
        refreshTokens.save(userId, tenantId, refreshToken.jti(), refreshToken.value(), refreshToken.expiresAt());
        var accessToken = tokens.issueAccessToken(userId, tenantId, membershipId, role);
        return new TokenPair(accessToken.value(), refreshToken.value());
    }

    public record TokenPair(String accessToken, String refreshToken) { }
}
