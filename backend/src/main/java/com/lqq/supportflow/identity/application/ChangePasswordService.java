package com.lqq.supportflow.identity.application;

import com.lqq.supportflow.identity.domain.RefreshTokenPort;
import com.lqq.supportflow.identity.domain.UserCredentialPort;
import java.time.Instant;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ChangePasswordService {

    private final UserCredentialPort credentials;
    private final RefreshTokenPort refreshTokens;
    private final PasswordEncoder passwordEncoder;

    public ChangePasswordService(UserCredentialPort credentials, RefreshTokenPort refreshTokens, PasswordEncoder passwordEncoder) {
        this.credentials = credentials;
        this.refreshTokens = refreshTokens;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional
    public void change(Long userId, Long tenantId, String currentPassword, String newPassword) {
        boolean matches = credentials.findActivePasswordHash(userId)
                .map(passwordHash -> passwordEncoder.matches(currentPassword, passwordHash))
                .orElse(false);
        if (!matches) {
            throw new BadCredentialsException("invalid credentials");
        }
        credentials.updatePasswordHash(userId, passwordEncoder.encode(newPassword));
        refreshTokens.revokeAllForUserInTenant(userId, tenantId, Instant.now());
    }
}
