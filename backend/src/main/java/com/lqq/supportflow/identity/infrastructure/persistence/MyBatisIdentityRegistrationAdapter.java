package com.lqq.supportflow.identity.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.lqq.supportflow.identity.domain.CustomerRegistration;
import com.lqq.supportflow.identity.domain.IdentityRegistrationPort;
import com.lqq.supportflow.identity.domain.MemberCreation;
import com.lqq.supportflow.identity.domain.MemberCreationResult;
import com.lqq.supportflow.identity.domain.MembershipManagementPort;
import com.lqq.supportflow.identity.domain.Role;
import com.lqq.supportflow.identity.domain.TenantAdminRegistration;
import com.lqq.supportflow.identity.domain.TenantAdminRegistrationResult;
import com.lqq.supportflow.identity.domain.UserCredentialPort;
import com.lqq.supportflow.shared.ActiveTenantProvider;
import com.lqq.supportflow.shared.AssignableMember;
import com.lqq.supportflow.shared.AssignableMemberProvider;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.OptionalLong;
import org.springframework.stereotype.Component;

@Component
public class MyBatisIdentityRegistrationAdapter implements IdentityRegistrationPort, MembershipManagementPort, UserCredentialPort, ActiveTenantProvider, AssignableMemberProvider {
    private final TenantMapper tenantMapper; private final UserMapper userMapper; private final TenantMembershipMapper membershipMapper;
    public MyBatisIdentityRegistrationAdapter(TenantMapper tenantMapper, UserMapper userMapper, TenantMembershipMapper membershipMapper) {
        this.tenantMapper = tenantMapper; this.userMapper = userMapper; this.membershipMapper = membershipMapper;
    }
    public boolean tenantCodeExists(String code) { return tenantMapper.exists(new QueryWrapper<TenantEntity>().eq("code", code)); }
    public boolean emailExists(String email) { return userMapper.exists(new QueryWrapper<UserEntity>().eq("email", email)); }
    public List<Long> findActiveTenantIds() {
        return tenantMapper.selectList(new QueryWrapper<TenantEntity>().eq("status", "ACTIVE"))
                .stream().map(tenant -> tenant.id).toList();
    }
    @Override
    public List<AssignableMember> findAssignableMembers(Long tenantId) {
        return membershipMapper.selectList(new QueryWrapper<TenantMembershipEntity>()
                        .eq("tenant_id", tenantId).eq("status", "ACTIVE")
                        .in("role", Role.TENANT_ADMIN.name(), Role.SUPERVISOR.name(), Role.AGENT.name()))
                .stream()
                .map(membership -> {
                    UserEntity user = userMapper.selectById(membership.userId);
                    return new AssignableMember(membership.id,
                            user == null ? "未知成员" : user.displayName,
                            membership.role);
                })
                .toList();
    }
    @Override
    public boolean isAssignable(Long tenantId, Long membershipId) {
        return membershipMapper.exists(new QueryWrapper<TenantMembershipEntity>()
                .eq("id", membershipId).eq("tenant_id", tenantId).eq("status", "ACTIVE")
                .in("role", Role.TENANT_ADMIN.name(), Role.SUPERVISOR.name(), Role.AGENT.name()));
    }
    public OptionalLong findActiveTenantIdByCode(String code) {
        TenantEntity tenant = tenantMapper.selectOne(new QueryWrapper<TenantEntity>().eq("code", code).eq("status", "ACTIVE"));
        return tenant == null ? OptionalLong.empty() : OptionalLong.of(tenant.id);
    }
    public TenantAdminRegistrationResult createTenantAdmin(TenantAdminRegistration data) {
        Instant now = Instant.now();
        TenantEntity tenant = new TenantEntity(); tenant.code=data.tenantCode(); tenant.name=data.tenantName(); tenant.status="ACTIVE"; tenant.createdAt=now; tenant.updatedAt=now; tenantMapper.insert(tenant);
        UserEntity user = new UserEntity(); user.email=data.email(); user.displayName=data.displayName(); user.passwordHash=data.passwordHash(); user.status="ACTIVE"; user.createdAt=now; user.updatedAt=now; userMapper.insert(user);
        TenantMembershipEntity membership = new TenantMembershipEntity(); membership.tenantId=tenant.id; membership.userId=user.id; membership.role=Role.TENANT_ADMIN.name(); membership.status="ACTIVE"; membership.createdAt=now; membership.updatedAt=now; membershipMapper.insert(membership);
        return new TenantAdminRegistrationResult(tenant.id, user.id, membership.id);
    }
    public TenantAdminRegistrationResult createCustomer(CustomerRegistration data) {
        Instant now = Instant.now();
        UserEntity user = new UserEntity(); user.email=data.email(); user.displayName=data.displayName(); user.passwordHash=data.passwordHash(); user.status="ACTIVE"; user.createdAt=now; user.updatedAt=now; userMapper.insert(user);
        TenantMembershipEntity membership = new TenantMembershipEntity(); membership.tenantId=data.tenantId(); membership.userId=user.id; membership.role=Role.CUSTOMER.name(); membership.status="ACTIVE"; membership.createdAt=now; membership.updatedAt=now; membershipMapper.insert(membership);
        return new TenantAdminRegistrationResult(data.tenantId(), user.id, membership.id);
    }

    @Override
    public MemberCreationResult createMember(MemberCreation data) {
        Instant now = Instant.now();
        UserEntity user = new UserEntity(); user.email=data.email(); user.displayName=data.displayName(); user.passwordHash=data.passwordHash(); user.status="ACTIVE"; user.createdAt=now; user.updatedAt=now; userMapper.insert(user);
        TenantMembershipEntity membership = new TenantMembershipEntity(); membership.tenantId=data.tenantId(); membership.userId=user.id; membership.role=data.role().name(); membership.status="ACTIVE"; membership.createdAt=now; membership.updatedAt=now; membershipMapper.insert(membership);
        return new MemberCreationResult(user.id, membership.id);
    }

    @Override
    public Optional<Long> changeStatus(Long tenantId, Long membershipId, String status) {
        TenantMembershipEntity membership = membershipMapper.selectOne(new QueryWrapper<TenantMembershipEntity>()
                .eq("id", membershipId).eq("tenant_id", tenantId));
        if (membership == null) return Optional.empty();
        membership.status = status;
        membership.updatedAt = Instant.now();
        membershipMapper.updateById(membership);
        return Optional.of(membership.userId);
    }

    @Override
    public Optional<String> findActivePasswordHash(Long userId) {
        UserEntity user = userMapper.selectOne(new QueryWrapper<UserEntity>().eq("id", userId).eq("status", "ACTIVE"));
        return user == null ? Optional.empty() : Optional.of(user.passwordHash);
    }

    @Override
    public void updatePasswordHash(Long userId, String passwordHash) {
        UserEntity user = new UserEntity();
        user.id = userId;
        user.passwordHash = passwordHash;
        user.updatedAt = Instant.now();
        userMapper.updateById(user);
    }
}
