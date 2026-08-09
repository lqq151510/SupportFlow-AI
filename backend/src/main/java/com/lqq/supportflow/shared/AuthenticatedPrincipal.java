package com.lqq.supportflow.shared;

public record AuthenticatedPrincipal(Long userId, Long tenantId, Long membershipId, String role) { }
