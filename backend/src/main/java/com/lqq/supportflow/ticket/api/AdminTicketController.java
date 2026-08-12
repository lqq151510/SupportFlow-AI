package com.lqq.supportflow.ticket.api;

import com.lqq.supportflow.commerce.CustomerOrderCatalogService;
import com.lqq.supportflow.conversation.AgentConversationViewService;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import com.lqq.supportflow.ticket.application.ManageTicketService;
import com.lqq.supportflow.ticket.domain.Ticket;
import com.lqq.supportflow.ticket.domain.TicketComment;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/admin/tickets")
public class AdminTicketController {
    private final ManageTicketService service;
    private final AgentConversationViewService conversations;
    private final CustomerOrderCatalogService orders;

    public AdminTicketController(ManageTicketService service, AgentConversationViewService conversations,
            CustomerOrderCatalogService orders) {
        this.service = service; this.conversations = conversations; this.orders = orders;
    }

    @GetMapping List<Ticket> list(@AuthenticationPrincipal AuthenticatedPrincipal principal) { return service.list(principal.tenantId()); }

    @GetMapping("/{ticketId}/context") TicketContext context(@AuthenticationPrincipal AuthenticatedPrincipal principal,
            @PathVariable Long ticketId) {
        Ticket ticket = service.get(principal.tenantId(), ticketId);
        return new TicketContext(ticket, conversations.get(principal.tenantId(), ticket.conversationId()),
                orders.list(principal.tenantId(), ticket.customerId()));
    }

    @PostMapping("/{ticketId}/claim") Ticket claim(@AuthenticationPrincipal AuthenticatedPrincipal principal,@PathVariable Long ticketId,@RequestHeader("Idempotency-Key") String idempotencyKey){return service.claim(principal.tenantId(),ticketId,principal.membershipId(),idempotencyKey);}
    @PostMapping("/{ticketId}/assign") Ticket assign(@AuthenticationPrincipal AuthenticatedPrincipal principal,@PathVariable Long ticketId,@Valid @RequestBody AssignTicketRequest request){return service.assign(principal.tenantId(),ticketId,request.membershipId(),principal.membershipId());}
    @PostMapping("/{ticketId}/status") Ticket status(@AuthenticationPrincipal AuthenticatedPrincipal principal,@PathVariable Long ticketId,@Valid @RequestBody ChangeTicketStatusRequest request){return service.changeStatus(principal.tenantId(),ticketId,request.status());}
    @GetMapping("/{ticketId}/comments") List<TicketComment> comments(@AuthenticationPrincipal AuthenticatedPrincipal principal,@PathVariable Long ticketId){return service.comments(principal.tenantId(),ticketId);}
    @PostMapping("/{ticketId}/comments") ResponseEntity<TicketComment> comment(@AuthenticationPrincipal AuthenticatedPrincipal principal,@PathVariable Long ticketId,@Valid @RequestBody TicketCommentRequest request){return ResponseEntity.status(HttpStatus.CREATED).body(service.addComment(principal.tenantId(),ticketId,principal.membershipId(),request.content()));}

    record TicketContext(Ticket ticket, AgentConversationViewService.ConversationView conversation,
                         List<CustomerOrderCatalogService.OrderView> orders) { }
}
