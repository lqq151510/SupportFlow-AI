package com.lqq.supportflow.model.api;
import com.lqq.supportflow.model.domain.ModelProtocol;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
public record CreateModelConfigRequest(@NotBlank String name,@NotNull ModelProtocol protocol,@NotBlank String baseUrl,@NotBlank String modelName,@NotBlank String apiKey,boolean isDefault) { }
