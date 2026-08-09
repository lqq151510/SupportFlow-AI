package com.lqq.supportflow.identity.api;

import jakarta.validation.constraints.NotBlank;

public record ChangeMemberStatusRequest(@NotBlank String status) { }
