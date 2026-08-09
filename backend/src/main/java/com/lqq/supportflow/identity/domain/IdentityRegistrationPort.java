package com.lqq.supportflow.identity.domain;

import java.util.List;
import java.util.OptionalLong;

public interface IdentityRegistrationPort {
    boolean tenantCodeExists(String tenantCode);
    boolean emailExists(String email);
    List<Long> findActiveTenantIds();
    OptionalLong findActiveTenantIdByCode(String tenantCode);
    TenantAdminRegistrationResult createTenantAdmin(TenantAdminRegistration registration);
    TenantAdminRegistrationResult createCustomer(CustomerRegistration registration);
}
