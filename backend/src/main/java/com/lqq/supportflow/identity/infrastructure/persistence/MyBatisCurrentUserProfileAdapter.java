package com.lqq.supportflow.identity.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.lqq.supportflow.identity.domain.CurrentUserProfile;
import com.lqq.supportflow.identity.domain.CurrentUserProfilePort;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import java.time.Instant;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Component;

@Component
public class MyBatisCurrentUserProfileAdapter implements CurrentUserProfilePort {
    private final UserMapper users;
    private final TenantMapper tenants;
    private final TenantMembershipMapper memberships;

    public MyBatisCurrentUserProfileAdapter(UserMapper users, TenantMapper tenants, TenantMembershipMapper memberships) {
        this.users = users;
        this.tenants = tenants;
        this.memberships = memberships;
    }

    @Override
    public CurrentUserProfile get(AuthenticatedPrincipal principal) {
        UserEntity user = requireUser(principal);
        TenantEntity tenant = requireTenant(principal);
        TenantMembershipEntity membership = requireMembership(principal);
        return new CurrentUserProfile(
                user.id, tenant.id, membership.id, user.displayName, user.email, membership.role,
                tenant.name, tenant.code, membership.createdAt);
    }

    @Override
    public CurrentUserProfile updateDisplayName(AuthenticatedPrincipal principal, String displayName) {
        users.update(null, new UpdateWrapper<UserEntity>()
                .eq("id", principal.userId())
                .set("display_name", displayName)
                .set("updated_at", Instant.now()));
        return get(principal);
    }

    private UserEntity requireUser(AuthenticatedPrincipal principal) {
        UserEntity user = users.selectById(principal.userId());
        if (user == null || !"ACTIVE".equals(user.status)) {
            throw new AccessDeniedException("active user not found");
        }
        return user;
    }

    private TenantEntity requireTenant(AuthenticatedPrincipal principal) {
        TenantEntity tenant = tenants.selectById(principal.tenantId());
        if (tenant == null || !"ACTIVE".equals(tenant.status)) {
            throw new AccessDeniedException("active tenant not found");
        }
        return tenant;
    }

    private TenantMembershipEntity requireMembership(AuthenticatedPrincipal principal) {
        TenantMembershipEntity membership = memberships.selectById(principal.membershipId());
        if (membership == null || !principal.tenantId().equals(membership.tenantId)
                || !principal.userId().equals(membership.userId) || !"ACTIVE".equals(membership.status)) {
            throw new AccessDeniedException("active membership not found");
        }
        return membership;
    }
}
