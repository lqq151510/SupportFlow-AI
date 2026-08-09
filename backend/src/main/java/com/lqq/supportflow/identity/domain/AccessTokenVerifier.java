package com.lqq.supportflow.identity.domain;

import java.util.Optional;

public interface AccessTokenVerifier {

    Optional<AccessTokenSubject> verifyAccessToken(String rawToken);
}
