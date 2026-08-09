package com.lqq.supportflow.identity.domain;

import java.time.Instant;

public interface RefreshTokenPort {

    void save(Long userId, Long tenantId, String jti, String rawToken, Instant expiresAt);

    boolean isActive(Long userId, Long tenantId, String jti, String rawToken, Instant now);

    void revoke(String jti, Instant revokedAt);

    void revokeAllForUserInTenant(Long userId, Long tenantId, Instant revokedAt);
}
