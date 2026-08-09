package com.lqq.supportflow.ticket.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.lqq.supportflow.ticket.domain.Ticket;
import com.lqq.supportflow.ticket.domain.TicketPort;
import com.lqq.supportflow.ticket.domain.TicketPriority;
import com.lqq.supportflow.ticket.domain.TicketStatus;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class MyBatisTicketAdapter implements TicketPort {
    private final TicketMapper mapper;

    public MyBatisTicketAdapter(TicketMapper mapper) { this.mapper = mapper; }

    @Override public Ticket create(Long tenantId, Long customerId, Long conversationId, String title, TicketPriority priority) {
        Instant now = Instant.now(); TicketEntity entity = new TicketEntity();
        entity.tenantId = tenantId; entity.customerId = customerId; entity.conversationId = conversationId; entity.title = title;
        entity.status = TicketStatus.NEW.name(); entity.priority = priority.name(); entity.firstResponseDueAt = now.plus(firstResponse(priority)); entity.resolutionDueAt = now.plus(resolution(priority)); entity.version = 0L; entity.createdAt = now; entity.updatedAt = now;
        mapper.insert(entity); return ticket(entity);
    }
    @Override public List<Ticket> list(Long tenantId) { return mapper.selectList(new QueryWrapper<TicketEntity>().eq("tenant_id", tenantId).orderByAsc("first_response_due_at")).stream().map(this::ticket).toList(); }
    @Override public Ticket claim(Long tenantId, Long ticketId, Long membershipId) { TicketEntity source = owned(tenantId, ticketId); int updated = mapper.update(new TicketEntity(), new UpdateWrapper<TicketEntity>().eq("id", ticketId).eq("tenant_id", tenantId).eq("version", source.version).isNull("assigned_membership_id").set("assigned_membership_id", membershipId).set("status", TicketStatus.OPEN.name()).set("updated_at", Instant.now()).setSql("version = version + 1")); if (updated != 1) throw new IllegalArgumentException("ticket has already been claimed"); return ticket(owned(tenantId, ticketId)); }
    @Override public Ticket changeStatus(Long tenantId, Long ticketId, TicketStatus target) { TicketEntity source = owned(tenantId, ticketId); TicketStatus current = TicketStatus.valueOf(source.status); if (!canTransition(current, target)) throw new IllegalArgumentException("invalid ticket status transition"); int updated = mapper.update(new TicketEntity(), new UpdateWrapper<TicketEntity>().eq("id", ticketId).eq("tenant_id", tenantId).eq("version", source.version).set("status", target.name()).set("updated_at", Instant.now()).setSql("version = version + 1")); if (updated != 1) throw new IllegalArgumentException("ticket was changed by another agent"); return ticket(owned(tenantId, ticketId)); }
    private TicketEntity owned(Long tenantId, Long ticketId) { TicketEntity entity = mapper.selectOne(new QueryWrapper<TicketEntity>().eq("id", ticketId).eq("tenant_id", tenantId)); if (entity == null) throw new IllegalArgumentException("ticket does not belong to tenant"); return entity; }
    private Ticket ticket(TicketEntity entity) { return new Ticket(entity.id, entity.customerId, entity.title, TicketStatus.valueOf(entity.status), TicketPriority.valueOf(entity.priority), entity.assignedMembershipId, entity.firstResponseDueAt, entity.resolutionDueAt); }
    private boolean canTransition(TicketStatus current, TicketStatus target) { return switch (current) { case NEW -> target == TicketStatus.OPEN; case OPEN -> target == TicketStatus.PENDING_CUSTOMER || target == TicketStatus.PENDING_APPROVAL || target == TicketStatus.RESOLVED; case PENDING_CUSTOMER, PENDING_APPROVAL -> target == TicketStatus.OPEN || target == TicketStatus.RESOLVED; case RESOLVED -> target == TicketStatus.OPEN || target == TicketStatus.CLOSED; case CLOSED -> false; }; }
    private Duration firstResponse(TicketPriority priority) { return switch (priority) { case LOW -> Duration.ofHours(8); case NORMAL -> Duration.ofHours(4); case HIGH -> Duration.ofHours(1); case URGENT -> Duration.ofMinutes(15); }; }
    private Duration resolution(TicketPriority priority) { return switch (priority) { case LOW -> Duration.ofHours(72); case NORMAL -> Duration.ofHours(48); case HIGH -> Duration.ofHours(12); case URGENT -> Duration.ofHours(4); }; }
}
