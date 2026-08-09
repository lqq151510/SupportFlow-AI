package com.lqq.supportflow.identity.domain;

import java.util.Optional;

public interface UserCredentialPort {

    Optional<String> findActivePasswordHash(Long userId);

    void updatePasswordHash(Long userId, String passwordHash);
}
