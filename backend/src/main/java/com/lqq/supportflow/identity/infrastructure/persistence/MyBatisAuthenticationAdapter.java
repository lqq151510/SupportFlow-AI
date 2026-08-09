package com.lqq.supportflow.identity.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.lqq.supportflow.identity.domain.AuthenticationPort;
import com.lqq.supportflow.identity.domain.LoginPrincipal;
import java.util.Optional;
import org.springframework.stereotype.Component;

@Component
public class MyBatisAuthenticationAdapter implements AuthenticationPort {
    private final TenantMapper tenants; private final UserMapper users; private final TenantMembershipMapper memberships;
    public MyBatisAuthenticationAdapter(TenantMapper tenants, UserMapper users, TenantMembershipMapper memberships) { this.tenants=tenants; this.users=users; this.memberships=memberships; }
    public Optional<LoginPrincipal> findActivePrincipal(String tenantCode, String email) {
        TenantEntity tenant=tenants.selectOne(new QueryWrapper<TenantEntity>().eq("code",tenantCode).eq("status","ACTIVE"));
        UserEntity user=users.selectOne(new QueryWrapper<UserEntity>().eq("email",email).eq("status","ACTIVE"));
        if (tenant==null || user==null) return Optional.empty();
        TenantMembershipEntity member=memberships.selectOne(new QueryWrapper<TenantMembershipEntity>().eq("tenant_id",tenant.id).eq("user_id",user.id).eq("status","ACTIVE"));
        return member==null ? Optional.empty() : Optional.of(new LoginPrincipal(user.id,tenant.id,member.id,member.role,user.passwordHash));
    }
}
