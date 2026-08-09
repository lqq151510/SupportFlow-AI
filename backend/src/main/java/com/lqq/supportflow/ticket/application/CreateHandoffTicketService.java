package com.lqq.supportflow.ticket.application;
import com.lqq.supportflow.conversation.HandoffRequiredEvent; import com.lqq.supportflow.ticket.domain.*; import org.springframework.context.event.EventListener; import org.springframework.stereotype.Service;
@Service public class CreateHandoffTicketService { private final TicketPort tickets; public CreateHandoffTicketService(TicketPort tickets){this.tickets=tickets;} @EventListener public void on(HandoffRequiredEvent event){tickets.create(event.tenantId(),event.customerId(),event.conversationId(),event.reason(),TicketPriority.NORMAL);}}
