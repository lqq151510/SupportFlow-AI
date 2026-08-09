package com.lqq.supportflow.identity.domain;

public record LoginPrincipal(Long userId, Long tenantId, Long membershipId, String role, String passwordHash) { }
