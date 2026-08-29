package com.lqq.supportflow.model.api;

import com.lqq.supportflow.model.domain.ModelProtocol;
import jakarta.validation.constraints.Size;

public record UpdateModelConfigRequest(
        @Size(max = 128) String name,
        ModelProtocol protocol,
        @Size(max = 512) String baseUrl,
        @Size(max = 128) String modelName,
        String apiKey,
        Boolean isDefault,
        Boolean isKnowledgeDefault) {
}
