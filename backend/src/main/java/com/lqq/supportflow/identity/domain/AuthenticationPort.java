package com.lqq.supportflow.identity.domain;

import java.util.Optional;

public interface AuthenticationPort {
    Optional<LoginPrincipal> findActivePrincipal(String tenantCode, String email);
}
