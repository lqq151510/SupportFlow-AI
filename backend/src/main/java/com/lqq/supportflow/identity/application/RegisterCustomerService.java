package com.lqq.supportflow.identity.application;

import com.lqq.supportflow.identity.domain.CustomerRegistration;
import com.lqq.supportflow.identity.domain.IdentityRegistrationPort;
import com.lqq.supportflow.identity.domain.TenantAdminRegistrationResult;
import com.lqq.supportflow.shared.ConflictException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RegisterCustomerService {
    private final IdentityRegistrationPort registrationPort; private final PasswordEncoder passwordEncoder;
    public RegisterCustomerService(IdentityRegistrationPort registrationPort, PasswordEncoder passwordEncoder) { this.registrationPort=registrationPort; this.passwordEncoder=passwordEncoder; }
    @Transactional
    public TenantAdminRegistrationResult register(String tenantCode, String email, String displayName, String password) {
        long tenantId = registrationPort.findActiveTenantIdByCode(tenantCode).orElseThrow(() -> new IllegalArgumentException("tenant code does not exist"));
        if (registrationPort.emailExists(email)) throw new ConflictException("email already exists");
        return registrationPort.createCustomer(new CustomerRegistration(tenantId, email, displayName, passwordEncoder.encode(password)));
    }
}
