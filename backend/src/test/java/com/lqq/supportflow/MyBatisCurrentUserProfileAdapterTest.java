package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.identity.infrastructure.persistence.MyBatisCurrentUserProfileAdapter;
import com.lqq.supportflow.identity.infrastructure.persistence.TenantEntity;
import com.lqq.supportflow.identity.infrastructure.persistence.TenantMapper;
import com.lqq.supportflow.identity.infrastructure.persistence.TenantMembershipEntity;
import com.lqq.supportflow.identity.infrastructure.persistence.TenantMembershipMapper;
import com.lqq.supportflow.identity.infrastructure.persistence.UserEntity;
import com.lqq.supportflow.identity.infrastructure.persistence.UserMapper;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.springframework.security.access.AccessDeniedException;

class MyBatisCurrentUserProfileAdapterTest {

    @Test
    void returnsAndUpdatesOnlyTheAuthenticatedActiveMembership() {
        UserMapper users = mock(UserMapper.class);
        TenantMapper tenants = mock(TenantMapper.class);
        TenantMembershipMapper memberships = mock(TenantMembershipMapper.class);
        AuthenticatedPrincipal principal = new AuthenticatedPrincipal(1L, 2L, 3L, "TENANT_ADMIN");
        UserEntity user = user("ACTIVE");
        TenantEntity tenant = tenant("ACTIVE");
        TenantMembershipEntity membership = membership(2L, 1L, "ACTIVE");
        when(users.selectById(1L)).thenReturn(user);
        when(tenants.selectById(2L)).thenReturn(tenant);
        when(memberships.selectById(3L)).thenReturn(membership);
        MyBatisCurrentUserProfileAdapter adapter = new MyBatisCurrentUserProfileAdapter(users, tenants, memberships);

        assertThat(adapter.get(principal))
                .extracting(profile -> profile.displayName(), profile -> profile.email(), profile -> profile.tenantName())
                .containsExactly("泽宝", "user@example.test", "SupportFlow 工作区");
        assertThat(adapter.updateDisplayName(principal, "开心" ).displayName()).isEqualTo("泽宝");
        verify(users).update(org.mockito.ArgumentMatchers.isNull(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    void rejectsInactiveOrForeignIdentityRecords() {
        UserMapper users = mock(UserMapper.class);
        TenantMapper tenants = mock(TenantMapper.class);
        TenantMembershipMapper memberships = mock(TenantMembershipMapper.class);
        AuthenticatedPrincipal principal = new AuthenticatedPrincipal(1L, 2L, 3L, "TENANT_ADMIN");
        MyBatisCurrentUserProfileAdapter adapter = new MyBatisCurrentUserProfileAdapter(users, tenants, memberships);

        when(users.selectById(1L)).thenReturn(null);
        assertDenied(() -> adapter.get(principal));
        when(users.selectById(1L)).thenReturn(user("DISABLED"));
        assertDenied(() -> adapter.get(principal));
        when(users.selectById(1L)).thenReturn(user("ACTIVE"));
        when(tenants.selectById(2L)).thenReturn(tenant("SUSPENDED"));
        assertDenied(() -> adapter.get(principal));
        when(tenants.selectById(2L)).thenReturn(tenant("ACTIVE"));
        when(memberships.selectById(3L)).thenReturn(null, membership(99L, 1L, "ACTIVE"), membership(2L, 99L, "ACTIVE"), membership(2L, 1L, "DISABLED"));
        assertDenied(() -> adapter.get(principal));
        assertDenied(() -> adapter.get(principal));
        assertDenied(() -> adapter.get(principal));
        assertDenied(() -> adapter.get(principal));
    }

    private void assertDenied(org.assertj.core.api.ThrowableAssert.ThrowingCallable action) {
        assertThatThrownBy(action).isInstanceOf(AccessDeniedException.class);
    }

    private UserEntity user(String status) {
        UserEntity entity = new UserEntity();
        entity.id = 1L; entity.displayName = "泽宝"; entity.email = "user@example.test"; entity.status = status;
        return entity;
    }

    private TenantEntity tenant(String status) {
        TenantEntity entity = new TenantEntity();
        entity.id = 2L; entity.name = "SupportFlow 工作区"; entity.code = "supportflow"; entity.status = status;
        return entity;
    }

    private TenantMembershipEntity membership(Long tenantId, Long userId, String status) {
        TenantMembershipEntity entity = new TenantMembershipEntity();
        entity.id = 3L; entity.tenantId = tenantId; entity.userId = userId; entity.role = "TENANT_ADMIN"; entity.status = status; entity.createdAt = Instant.now();
        return entity;
    }
}
