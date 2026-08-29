package com.lqq.supportflow.identity.application;

import com.lqq.supportflow.identity.domain.IdentityRegistrationPort;
import com.lqq.supportflow.identity.domain.TenantAdminRegistration;
import com.lqq.supportflow.identity.domain.TenantAdminRegistrationResult;
import com.lqq.supportflow.shared.ConflictException;
import java.util.UUID;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RegisterTenantAdminService {
    public record Registration(TenantAdminRegistrationResult result, String tenantCode) { }
    private final IdentityRegistrationPort registrationPort;
    private final PasswordEncoder passwordEncoder;

    public RegisterTenantAdminService(IdentityRegistrationPort registrationPort, PasswordEncoder passwordEncoder) {
        this.registrationPort = registrationPort;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional
    public Registration register(String requestedTenantCode, String requestedTenantName, String email, String displayName, String password) {
        String tenantCode = resolveTenantCode(requestedTenantCode);
        String tenantName = requestedTenantName == null || requestedTenantName.isBlank() ? displayName + " 的工作区" : requestedTenantName;
        if (registrationPort.tenantCodeExists(tenantCode)) throw new ConflictException("tenant code already exists");
        if (registrationPort.emailExists(email)) throw new ConflictException("email already exists");
        return new Registration(registrationPort.createTenantAdmin(new TenantAdminRegistration(
                tenantCode, tenantName, email, displayName, passwordEncoder.encode(password))), tenantCode);
    }

    private String resolveTenantCode(String requestedTenantCode) {
        if (requestedTenantCode != null && !requestedTenantCode.isBlank()) return requestedTenantCode;
        for (int attempts = 0; attempts < 8; attempts++) {
            String generated = "workspace-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
            if (!registrationPort.tenantCodeExists(generated)) return generated;
        }
        throw new IllegalStateException("cannot allocate workspace code");
    }
}
