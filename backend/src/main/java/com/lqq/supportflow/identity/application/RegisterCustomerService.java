package com.lqq.supportflow.identity.application;

import com.lqq.supportflow.identity.domain.CustomerRegistration;
import com.lqq.supportflow.identity.domain.IdentityRegistrationPort;
import com.lqq.supportflow.identity.domain.TenantAdminRegistrationResult;
import com.lqq.supportflow.identity.CustomerRegisteredEvent;
import com.lqq.supportflow.shared.ConflictException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RegisterCustomerService {
    private final IdentityRegistrationPort registrationPort; private final PasswordEncoder passwordEncoder; private final ApplicationEventPublisher events;
    public RegisterCustomerService(IdentityRegistrationPort registrationPort, PasswordEncoder passwordEncoder, ApplicationEventPublisher events) { this.registrationPort=registrationPort; this.passwordEncoder=passwordEncoder; this.events=events; }
    @Transactional
    public TenantAdminRegistrationResult register(String tenantCode, String email, String displayName, String password) {
        long tenantId = registrationPort.findActiveTenantIdByCode(tenantCode).orElseThrow(() -> new IllegalArgumentException("tenant code does not exist"));
        if (registrationPort.emailExists(email)) throw new ConflictException("email already exists");
        TenantAdminRegistrationResult result = registrationPort.createCustomer(new CustomerRegistration(tenantId, email, displayName, passwordEncoder.encode(password)));
        events.publishEvent(new CustomerRegisteredEvent(result.tenantId(), result.userId()));
        return result;
    }
}
