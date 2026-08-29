package com.lqq.supportflow.identity.domain;

import java.time.Instant;

public record CurrentUserProfile(
        Long userId,
        Long tenantId,
        Long membershipId,
        String displayName,
        String email,
        String role,
        String tenantName,
        String tenantCode,
        Instant joinedAt) {
}
