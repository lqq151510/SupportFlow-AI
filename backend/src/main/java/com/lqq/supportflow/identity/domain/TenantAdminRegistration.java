package com.lqq.supportflow.identity.domain;

public record TenantAdminRegistration(String tenantCode, String tenantName, String email, String displayName, String passwordHash) { }
