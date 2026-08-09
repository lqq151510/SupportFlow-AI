package com.lqq.supportflow.identity.api;

import com.lqq.supportflow.identity.application.ChangeMemberStatusService;
import com.lqq.supportflow.identity.application.CreateMemberService;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import jakarta.validation.Valid;
import java.net.URI;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/admin/members")
public class AdminMemberController {

    private final CreateMemberService createMembers;
    private final ChangeMemberStatusService changeStatus;

    public AdminMemberController(CreateMemberService createMembers, ChangeMemberStatusService changeStatus) {
        this.createMembers = createMembers;
        this.changeStatus = changeStatus;
    }

    @PostMapping
    ResponseEntity<MemberResponse> create(
            @AuthenticationPrincipal AuthenticatedPrincipal principal,
            @Valid @RequestBody CreateMemberRequest request) {
        var result = createMembers.create(principal.tenantId(), request.email(), request.displayName(), request.password(), request.role());
        return ResponseEntity.created(URI.create("/api/v1/admin/members/" + result.membershipId()))
                .body(new MemberResponse(result.userId(), result.membershipId()));
    }

    @PatchMapping("/{membershipId}/status")
    ResponseEntity<Void> changeStatus(
            @AuthenticationPrincipal AuthenticatedPrincipal principal,
            @PathVariable Long membershipId,
            @Valid @RequestBody ChangeMemberStatusRequest request) {
        changeStatus.change(principal.tenantId(), membershipId, request.status());
        return ResponseEntity.noContent().build();
    }

    record MemberResponse(Long userId, Long membershipId) { }
}
