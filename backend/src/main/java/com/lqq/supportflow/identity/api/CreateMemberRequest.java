package com.lqq.supportflow.identity.api;

import com.lqq.supportflow.identity.domain.Role;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record CreateMemberRequest(
        @NotBlank @Email String email,
        @NotBlank @Size(max = 128) String displayName,
        @NotBlank @Size(min = 12, max = 128) String password,
        @NotNull Role role) { }
