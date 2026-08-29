package com.lqq.supportflow.identity.application;

import com.lqq.supportflow.identity.domain.CurrentUserProfile;
import com.lqq.supportflow.identity.domain.CurrentUserProfilePort;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CurrentUserProfileService {
    private final CurrentUserProfilePort profiles;

    public CurrentUserProfileService(CurrentUserProfilePort profiles) {
        this.profiles = profiles;
    }

    @Transactional(readOnly = true)
    public CurrentUserProfile get(AuthenticatedPrincipal principal) {
        return profiles.get(principal);
    }

    @Transactional
    public CurrentUserProfile updateDisplayName(AuthenticatedPrincipal principal, String displayName) {
        String normalized = displayName.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException("display name must not be blank");
        }
        return profiles.updateDisplayName(principal, normalized);
    }
}
