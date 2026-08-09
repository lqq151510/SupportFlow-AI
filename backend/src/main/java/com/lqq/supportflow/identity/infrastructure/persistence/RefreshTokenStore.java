package com.lqq.supportflow.identity.infrastructure.persistence;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import org.springframework.stereotype.Component;
import com.lqq.supportflow.identity.domain.RefreshTokenPort;

@Component
public class RefreshTokenStore implements RefreshTokenPort {
    private final RefreshTokenMapper mapper;
    public RefreshTokenStore(RefreshTokenMapper mapper) { this.mapper = mapper; }
    public void save(Long userId, Long tenantId, String jti, String rawToken, Instant expiresAt) {
        RefreshTokenEntity token = new RefreshTokenEntity(); token.userId=userId; token.tenantId=tenantId; token.jti=jti;
        token.tokenHash=hash(rawToken); token.expiresAt=expiresAt; token.createdAt=Instant.now(); mapper.insert(token);
    }
    private String hash(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch (Exception exception) { throw new IllegalStateException("SHA-256 is unavailable", exception); }
    }
}
