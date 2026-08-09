package com.lqq.supportflow.model.domain;

import reactor.core.publisher.Flux;

public interface ChatModelGateway {

    Flux<ModelEvent> stream(ChatModelRequest request);
}
