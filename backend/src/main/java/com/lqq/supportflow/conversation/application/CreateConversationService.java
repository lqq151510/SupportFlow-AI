package com.lqq.supportflow.conversation.application;
import com.lqq.supportflow.conversation.domain.*; import org.springframework.stereotype.Service;
@Service public class CreateConversationService { private final ConversationPort conversations; public CreateConversationService(ConversationPort conversations){this.conversations=conversations;} public Conversation create(Long tenantId,Long customerId){return conversations.create(tenantId,customerId);}}
