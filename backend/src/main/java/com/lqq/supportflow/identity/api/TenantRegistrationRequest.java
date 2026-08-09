package com.lqq.supportflow.identity.api;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record TenantRegistrationRequest(
        @NotBlank @Pattern(regexp = "[a-z0-9-]{3,64}") String tenantCode,
        @NotBlank @Size(max = 128) String tenantName,
        @NotBlank @Email @Size(max = 254) String email,
        @NotBlank @Size(max = 128) String displayName,
        @NotBlank @Size(min = 12, max = 72) String password) { }
