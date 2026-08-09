package com.lqq.supportflow.commerce.domain;

import java.math.BigDecimal;
import java.time.Instant;

public record CustomerOrder(
        String orderNo,
        String status,
        BigDecimal totalAmount,
        String currency,
        Instant createdAt) { }
