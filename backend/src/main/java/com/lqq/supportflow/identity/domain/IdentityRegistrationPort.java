package com.lqq.supportflow.identity.domain;

public interface IdentityRegistrationPort {
    boolean tenantCodeExists(String tenantCode);
    boolean emailExists(String email);
    TenantAdminRegistrationResult createTenantAdmin(TenantAdminRegistration registration);
}
