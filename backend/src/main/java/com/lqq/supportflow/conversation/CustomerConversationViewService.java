package com.lqq.supportflow.conversation;

import com.lqq.supportflow.conversation.domain.ConversationPort;
import org.springframework.stereotype.Service;

@Service
public class CustomerConversationViewService {
    private final ConversationPort conversations;
    private final AgentConversationViewService views;

    public CustomerConversationViewService(ConversationPort conversations, AgentConversationViewService views) {
        this.conversations = conversations; this.views = views;
    }

    public AgentConversationViewService.ConversationView get(Long tenantId, Long customerId, Long conversationId) {
        if (!conversations.belongsTo(tenantId, customerId, conversationId)) {
            throw new IllegalArgumentException("conversation does not belong to customer");
        }
        AgentConversationViewService.ConversationView view = views.get(tenantId, conversationId);
        return new AgentConversationViewService.ConversationView(view.messages(), java.util.List.of());
    }
}
