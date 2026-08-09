package com.lqq.supportflow.eventing.domain;

public interface OutboxDeliveryGateway { void publish(OutboxEvent event); }
