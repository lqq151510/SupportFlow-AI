package com.lqq.supportflow.model.domain;

import java.util.List;

public record EmbeddingRequest(Long tenantId, List<String> inputs) { }
