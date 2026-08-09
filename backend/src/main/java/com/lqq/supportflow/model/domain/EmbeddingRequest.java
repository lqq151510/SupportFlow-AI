package com.lqq.supportflow.model.domain;

import java.util.List;

public record EmbeddingRequest(String model, List<String> inputs) { }
