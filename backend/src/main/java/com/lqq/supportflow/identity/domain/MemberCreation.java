package com.lqq.supportflow.identity.domain;

public record MemberCreation(Long tenantId, String email, String displayName, String passwordHash, Role role) { }
