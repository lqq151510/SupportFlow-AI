package com.lqq.supportflow.identity.api;

import com.lqq.supportflow.identity.application.RegisterTenantAdminService;
import com.lqq.supportflow.identity.domain.TenantAdminRegistrationResult;
import jakarta.validation.Valid;
import java.net.URI;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/tenants")
public class TenantRegistrationController {
    private final RegisterTenantAdminService service;
    public TenantRegistrationController(RegisterTenantAdminService service) { this.service = service; }
    @PostMapping("/register")
    ResponseEntity<TenantRegistrationResponse> register(@Valid @RequestBody TenantRegistrationRequest request) {
        TenantAdminRegistrationResult result = service.register(request.tenantCode(), request.tenantName(), request.email(), request.displayName(), request.password());
        return ResponseEntity.created(URI.create("/api/v1/tenants/" + result.tenantId())).body(new TenantRegistrationResponse(
                result.tenantId().toString(), result.userId().toString(), result.membershipId().toString()));
    }
}
