package com.lqq.supportflow.identity.domain;

import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import java.util.Optional;

public interface AccessTokenVerifier {

    Optional<AuthenticatedPrincipal> verifyAccessToken(String rawToken);
}
