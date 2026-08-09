package com.lqq.supportflow.commerce.domain;
import java.time.Instant;
public record Shipment(String orderNo,String trackingNo,String carrier,String status,Instant estimatedDeliveryAt) { }
