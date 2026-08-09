package com.lqq.supportflow.identity.application;

import com.lqq.supportflow.identity.domain.IdentityRegistrationPort;
import com.lqq.supportflow.identity.domain.TenantAdminRegistration;
import com.lqq.supportflow.identity.domain.TenantAdminRegistrationResult;
import com.lqq.supportflow.shared.ConflictException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RegisterTenantAdminService {
    private final IdentityRegistrationPort registrationPort;
    private final PasswordEncoder passwordEncoder;

    public RegisterTenantAdminService(IdentityRegistrationPort registrationPort, PasswordEncoder passwordEncoder) {
        this.registrationPort = registrationPort;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional
    public TenantAdminRegistrationResult register(String tenantCode, String tenantName, String email, String displayName, String password) {
        if (registrationPort.tenantCodeExists(tenantCode)) throw new ConflictException("tenant code already exists");
        if (registrationPort.emailExists(email)) throw new ConflictException("email already exists");
        return registrationPort.createTenantAdmin(new TenantAdminRegistration(
                tenantCode, tenantName, email, displayName, passwordEncoder.encode(password)));
    }
}
