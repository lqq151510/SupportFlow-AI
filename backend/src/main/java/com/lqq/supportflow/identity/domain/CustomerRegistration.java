package com.lqq.supportflow.identity.domain;

public record CustomerRegistration(Long tenantId, String email, String displayName, String passwordHash) { }
