package com.lqq.supportflow.shared;

import java.util.List;

public interface AssignableMemberProvider {
    List<AssignableMember> findAssignableMembers(Long tenantId);

    boolean isAssignable(Long tenantId, Long membershipId);
}
