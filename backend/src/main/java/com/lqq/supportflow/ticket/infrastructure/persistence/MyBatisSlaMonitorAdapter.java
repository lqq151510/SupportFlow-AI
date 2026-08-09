package com.lqq.supportflow.ticket.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.lqq.supportflow.ticket.SlaDeadline;
import com.lqq.supportflow.ticket.domain.SlaMonitorPort;
import com.lqq.supportflow.ticket.domain.TicketStatus;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Component;

@Component
public class MyBatisSlaMonitorAdapter implements SlaMonitorPort {
    private final TicketMapper tickets;
    private final TicketSlaAlertMapper alerts;

    public MyBatisSlaMonitorAdapter(TicketMapper tickets, TicketSlaAlertMapper alerts) {
        this.tickets = tickets;
        this.alerts = alerts;
    }

    @Override
    public List<SlaDeadline> dueAt(Instant now) {
        List<SlaDeadline> deadlines = new ArrayList<>();
        for (TicketEntity ticket : tickets.selectList(new QueryWrapper<TicketEntity>().le("first_response_due_at", now).eq("status", TicketStatus.NEW.name()))) {
            deadlines.add(new SlaDeadline(ticket.tenantId, ticket.id, "FIRST_RESPONSE", ticket.firstResponseDueAt));
        }
        for (TicketEntity ticket : tickets.selectList(new QueryWrapper<TicketEntity>().le("resolution_due_at", now).notIn("status", TicketStatus.RESOLVED.name(), TicketStatus.CLOSED.name()))) {
            deadlines.add(new SlaDeadline(ticket.tenantId, ticket.id, "RESOLUTION", ticket.resolutionDueAt));
        }
        return deadlines;
    }

    @Override
    public boolean markAlerted(SlaDeadline deadline) {
        TicketSlaAlertEntity alert = new TicketSlaAlertEntity();
        alert.tenantId = deadline.tenantId();
        alert.ticketId = deadline.ticketId();
        alert.alertType = deadline.type();
        alert.dueAt = deadline.dueAt();
        alert.alertedAt = Instant.now();
        try {
            return alerts.insert(alert) == 1;
        } catch (DuplicateKeyException ignored) {
            return false;
        }
    }
}
