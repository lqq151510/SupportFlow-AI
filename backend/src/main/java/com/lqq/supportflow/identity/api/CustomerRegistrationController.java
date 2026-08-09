package com.lqq.supportflow.identity.api;

import com.lqq.supportflow.identity.application.RegisterCustomerService;
import com.lqq.supportflow.identity.domain.TenantAdminRegistrationResult;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/customers")
public class CustomerRegistrationController {
    private final RegisterCustomerService service;
    public CustomerRegistrationController(RegisterCustomerService service) { this.service = service; }
    @PostMapping("/register")
    ResponseEntity<TenantRegistrationResponse> register(@Valid @RequestBody CustomerRegistrationRequest request) {
        TenantAdminRegistrationResult result = service.register(request.tenantCode(), request.email(), request.displayName(), request.password());
        return ResponseEntity.status(201).body(new TenantRegistrationResponse(result.tenantId().toString(), result.userId().toString(), result.membershipId().toString()));
    }
}
