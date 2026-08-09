package com.lqq.supportflow.identity.api;
import jakarta.validation.constraints.*;
public record LoginRequest(@NotBlank String tenantCode,@NotBlank @Email String email,@NotBlank String password) { }
