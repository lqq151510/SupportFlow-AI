package com.lqq.supportflow.identity.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
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

    @Override
    public boolean isActive(Long userId, Long tenantId, String jti, String rawToken, Instant now) {
        RefreshTokenEntity token = mapper.selectOne(new QueryWrapper<RefreshTokenEntity>()
                .eq("jti", jti)
                .eq("user_id", userId)
                .eq("tenant_id", tenantId));
        return token != null
                && token.revokedAt == null
                && token.expiresAt.isAfter(now)
                && MessageDigest.isEqual(token.tokenHash.getBytes(StandardCharsets.UTF_8), hash(rawToken).getBytes(StandardCharsets.UTF_8));
    }

    @Override
    public void revoke(String jti, Instant revokedAt) {
        RefreshTokenEntity token = new RefreshTokenEntity();
        token.revokedAt = revokedAt;
        mapper.update(token, new QueryWrapper<RefreshTokenEntity>().eq("jti", jti).isNull("revoked_at"));
    }
    private String hash(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch (Exception exception) { throw new IllegalStateException("SHA-256 is unavailable", exception); }
    }
}
