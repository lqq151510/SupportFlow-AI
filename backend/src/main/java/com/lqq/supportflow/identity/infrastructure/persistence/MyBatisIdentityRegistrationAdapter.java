package com.lqq.supportflow.identity.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.lqq.supportflow.identity.domain.IdentityRegistrationPort;
import com.lqq.supportflow.identity.domain.Role;
import com.lqq.supportflow.identity.domain.TenantAdminRegistration;
import com.lqq.supportflow.identity.domain.TenantAdminRegistrationResult;
import java.time.Instant;
import org.springframework.stereotype.Component;

@Component
public class MyBatisIdentityRegistrationAdapter implements IdentityRegistrationPort {
    private final TenantMapper tenantMapper; private final UserMapper userMapper; private final TenantMembershipMapper membershipMapper;
    public MyBatisIdentityRegistrationAdapter(TenantMapper tenantMapper, UserMapper userMapper, TenantMembershipMapper membershipMapper) {
        this.tenantMapper = tenantMapper; this.userMapper = userMapper; this.membershipMapper = membershipMapper;
    }
    public boolean tenantCodeExists(String code) { return tenantMapper.exists(new QueryWrapper<TenantEntity>().eq("code", code)); }
    public boolean emailExists(String email) { return userMapper.exists(new QueryWrapper<UserEntity>().eq("email", email)); }
    public TenantAdminRegistrationResult createTenantAdmin(TenantAdminRegistration data) {
        Instant now = Instant.now();
        TenantEntity tenant = new TenantEntity(); tenant.code=data.tenantCode(); tenant.name=data.tenantName(); tenant.status="ACTIVE"; tenant.createdAt=now; tenant.updatedAt=now; tenantMapper.insert(tenant);
        UserEntity user = new UserEntity(); user.email=data.email(); user.displayName=data.displayName(); user.passwordHash=data.passwordHash(); user.status="ACTIVE"; user.createdAt=now; user.updatedAt=now; userMapper.insert(user);
        TenantMembershipEntity membership = new TenantMembershipEntity(); membership.tenantId=tenant.id; membership.userId=user.id; membership.role=Role.TENANT_ADMIN.name(); membership.status="ACTIVE"; membership.createdAt=now; membership.updatedAt=now; membershipMapper.insert(membership);
        return new TenantAdminRegistrationResult(tenant.id, user.id, membership.id);
    }
}
