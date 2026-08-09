package com.lqq.supportflow.identity.application;

import com.lqq.supportflow.identity.domain.MembershipManagementPort;
import com.lqq.supportflow.identity.domain.RefreshTokenPort;
import java.time.Instant;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ChangeMemberStatusService {

    private final MembershipManagementPort memberships;
    private final RefreshTokenPort refreshTokens;

    public ChangeMemberStatusService(MembershipManagementPort memberships, RefreshTokenPort refreshTokens) {
        this.memberships = memberships;
        this.refreshTokens = refreshTokens;
    }

    @Transactional
    public void change(Long tenantId, Long membershipId, String status) {
        if (!"ACTIVE".equals(status) && !"DISABLED".equals(status)) {
            throw new IllegalArgumentException("status must be ACTIVE or DISABLED");
        }
        Long userId = memberships.changeStatus(tenantId, membershipId, status)
                .orElseThrow(() -> new IllegalArgumentException("membership does not belong to tenant"));
        if ("DISABLED".equals(status)) {
            refreshTokens.revokeAllForUserInTenant(userId, tenantId, Instant.now());
        }
    }
}
