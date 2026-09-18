package com.lqq.supportflow.conversation.api;

import com.lqq.supportflow.conversation.AgentConversationViewService;
import com.lqq.supportflow.conversation.CustomerConversationViewService;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/customer/conversations")
public class CustomerConversationController {
    private final CustomerConversationViewService conversations;

    public CustomerConversationController(CustomerConversationViewService conversations) { this.conversations = conversations; }

    @GetMapping("/{conversationId}")
    AgentConversationViewService.ConversationView get(@AuthenticationPrincipal AuthenticatedPrincipal principal,
            @PathVariable Long conversationId) {
        return conversations.get(principal.tenantId(), principal.userId(), conversationId);
    }
}
