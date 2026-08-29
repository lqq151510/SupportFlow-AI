package com.lqq.supportflow.identity.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record UpdateCurrentUserProfileRequest(
        @NotBlank @Size(max = 128) String displayName) {
}
