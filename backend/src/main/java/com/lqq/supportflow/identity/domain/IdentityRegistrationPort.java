package com.lqq.supportflow.identity.domain;

import java.util.OptionalLong;

public interface IdentityRegistrationPort {
    boolean tenantCodeExists(String tenantCode);
    boolean emailExists(String email);
    OptionalLong findActiveTenantIdByCode(String tenantCode);
    TenantAdminRegistrationResult createTenantAdmin(TenantAdminRegistration registration);
    TenantAdminRegistrationResult createCustomer(CustomerRegistration registration);
}
