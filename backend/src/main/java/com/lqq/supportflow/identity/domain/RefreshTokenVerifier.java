package com.lqq.supportflow.identity.domain;

import java.util.Optional;

public interface RefreshTokenVerifier {

    Optional<RefreshTokenSubject> verify(String rawToken);
}
