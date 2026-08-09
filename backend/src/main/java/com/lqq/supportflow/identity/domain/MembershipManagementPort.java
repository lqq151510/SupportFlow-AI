package com.lqq.supportflow.identity.domain;

import java.util.Optional;

public interface MembershipManagementPort {

    MemberCreationResult createMember(MemberCreation creation);

    Optional<Long> changeStatus(Long tenantId, Long membershipId, String status);
}
