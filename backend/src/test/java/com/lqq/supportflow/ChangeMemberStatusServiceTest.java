package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.identity.application.ChangeMemberStatusService;
import com.lqq.supportflow.identity.domain.MembershipManagementPort;
import com.lqq.supportflow.identity.domain.RefreshTokenPort;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class ChangeMemberStatusServiceTest {

    @Test
    void revokesTenantRefreshTokensWhenDisablingAMember() {
        MembershipManagementPort memberships = mock(MembershipManagementPort.class);
        RefreshTokenPort refreshTokens = mock(RefreshTokenPort.class);
        when(memberships.changeStatus(7L, 8L, "DISABLED")).thenReturn(Optional.of(9L));

        new ChangeMemberStatusService(memberships, refreshTokens).change(7L, 8L, "DISABLED");

        verify(refreshTokens).revokeAllForUserInTenant(org.mockito.ArgumentMatchers.eq(9L),
                org.mockito.ArgumentMatchers.eq(7L), org.mockito.ArgumentMatchers.any());
    }

    @Test
    void allowsActiveStatusWithoutRevokingTokensAndRejectsInvalidStatuses() {
        MembershipManagementPort memberships = mock(MembershipManagementPort.class);
        RefreshTokenPort refreshTokens = mock(RefreshTokenPort.class);
        when(memberships.changeStatus(7L, 8L, "ACTIVE")).thenReturn(Optional.of(9L));
        ChangeMemberStatusService service = new ChangeMemberStatusService(memberships, refreshTokens);

        service.change(7L, 8L, "ACTIVE");
        verifyNoInteractions(refreshTokens);
        assertThatThrownBy(() -> service.change(7L, 8L, "PENDING"))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("status must be ACTIVE or DISABLED");
    }

    @Test
    void rejectsMembershipsOutsideTheTenant() {
        MembershipManagementPort memberships = mock(MembershipManagementPort.class);
        when(memberships.changeStatus(7L, 8L, "ACTIVE")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> new ChangeMemberStatusService(memberships, mock(RefreshTokenPort.class))
                .change(7L, 8L, "ACTIVE"))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("membership does not belong to tenant");
    }
}
