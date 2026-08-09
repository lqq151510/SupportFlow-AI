package com.lqq.supportflow.identity.infrastructure.security;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "supportflow.jwt")
public record JwtProperties(String secretBase64, Duration accessTokenTtl, Duration refreshTokenTtl) { }
