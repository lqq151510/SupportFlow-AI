package com.lqq.supportflow.identity.domain;

public record RefreshTokenSubject(Long userId, Long tenantId, Long membershipId, String role, String jti) { }
