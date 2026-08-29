package com.lqq.supportflow.identity.domain;

import com.lqq.supportflow.shared.AuthenticatedPrincipal;

public interface CurrentUserProfilePort {
    CurrentUserProfile get(AuthenticatedPrincipal principal);

    CurrentUserProfile updateDisplayName(AuthenticatedPrincipal principal, String displayName);
}
