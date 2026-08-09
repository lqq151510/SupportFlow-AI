package com.lqq.supportflow.identity.domain;

import java.time.Instant;

public record IssuedToken(String value, String jti, Instant expiresAt) { }
