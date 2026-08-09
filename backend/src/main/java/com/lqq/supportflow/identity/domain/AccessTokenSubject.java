package com.lqq.supportflow.identity.domain;

public record AccessTokenSubject(Long userId, Long tenantId, Long membershipId, String role) { }
