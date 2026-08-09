package com.lqq.supportflow.model.domain;

import java.util.List;

public interface EmbeddingGateway {

    List<float[]> embedBatch(EmbeddingRequest request);
}
