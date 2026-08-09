package com.lqq.supportflow.eventing.domain;
public interface ConsumerLedger { boolean claim(Long tenantId,String consumerName,Long eventId); }
