package com.lqq.supportflow.identity.api;

import com.lqq.supportflow.identity.application.ChangeMemberStatusService;
import com.lqq.supportflow.identity.application.CreateMemberService;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import com.lqq.supportflow.shared.AssignableMemberProvider;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
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
    private final AssignableMemberProvider assignableMembers;

    public AdminMemberController(CreateMemberService createMembers, ChangeMemberStatusService changeStatus,
            AssignableMemberProvider assignableMembers) {
        this.createMembers = createMembers;
        this.changeStatus = changeStatus;
        this.assignableMembers = assignableMembers;
    }

    @GetMapping
    List<AssignableMemberResponse> list(@AuthenticationPrincipal AuthenticatedPrincipal principal) {
        return assignableMembers.findAssignableMembers(principal.tenantId()).stream()
                .map(member -> new AssignableMemberResponse(member.membershipId().toString(), member.displayName(), member.role()))
                .toList();
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
    record AssignableMemberResponse(String membershipId, String displayName, String role) { }
}
