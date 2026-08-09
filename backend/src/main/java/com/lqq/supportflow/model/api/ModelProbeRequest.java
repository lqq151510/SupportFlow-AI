package com.lqq.supportflow.model.api;
import jakarta.validation.constraints.NotBlank;
public record ModelProbeRequest(@NotBlank String baseUrl,@NotBlank String apiKey) { }
