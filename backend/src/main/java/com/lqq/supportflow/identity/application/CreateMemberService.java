package com.lqq.supportflow.identity.application;

import com.lqq.supportflow.identity.domain.IdentityRegistrationPort;
import com.lqq.supportflow.identity.domain.MemberCreation;
import com.lqq.supportflow.identity.domain.MemberCreationResult;
import com.lqq.supportflow.identity.domain.MembershipManagementPort;
import com.lqq.supportflow.identity.domain.Role;
import com.lqq.supportflow.shared.ConflictException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CreateMemberService {

    private final IdentityRegistrationPort registrations;
    private final MembershipManagementPort memberships;
    private final PasswordEncoder passwordEncoder;

    public CreateMemberService(IdentityRegistrationPort registrations, MembershipManagementPort memberships, PasswordEncoder passwordEncoder) {
        this.registrations = registrations;
        this.memberships = memberships;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional
    public MemberCreationResult create(Long tenantId, String email, String displayName, String password, Role role) {
        if (role != Role.SUPERVISOR && role != Role.AGENT) {
            throw new IllegalArgumentException("administrators may only create supervisors or agents");
        }
        if (registrations.emailExists(email)) {
            throw new ConflictException("email already exists");
        }
        return memberships.createMember(new MemberCreation(tenantId, email, displayName, passwordEncoder.encode(password), role));
    }
}
