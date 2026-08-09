package com.lqq.supportflow.identity.domain;
import java.time.Instant;
public interface RefreshTokenPort { void save(Long userId, Long tenantId, String jti, String rawToken, Instant expiresAt); }
