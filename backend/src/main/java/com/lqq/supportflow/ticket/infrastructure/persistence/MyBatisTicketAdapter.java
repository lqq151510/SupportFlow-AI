package com.lqq.supportflow.ticket.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.lqq.supportflow.ticket.domain.Ticket;
import com.lqq.supportflow.ticket.domain.TicketPort;
import com.lqq.supportflow.ticket.domain.TicketPriority;
import com.lqq.supportflow.ticket.domain.TicketStatus;
import com.lqq.supportflow.shared.ConflictException;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class MyBatisTicketAdapter implements TicketPort {
    private final TicketMapper mapper;
    private final TicketAssignmentMapper assignments;

    public MyBatisTicketAdapter(TicketMapper mapper, TicketAssignmentMapper assignments) { this.mapper = mapper; this.assignments = assignments; }

    @Override public Ticket create(Long tenantId, Long customerId, Long conversationId, String title, TicketPriority priority) {
        Instant now = Instant.now(); TicketEntity entity = new TicketEntity();
        entity.tenantId = tenantId; entity.customerId = customerId; entity.conversationId = conversationId; entity.title = title;
        entity.status = TicketStatus.NEW.name(); entity.priority = priority.name(); entity.firstResponseDueAt = now.plus(firstResponse(priority)); entity.resolutionDueAt = now.plus(resolution(priority)); entity.version = 0L; entity.createdAt = now; entity.updatedAt = now;
        mapper.insert(entity); return ticket(entity);
    }
    @Override public List<Ticket> list(Long tenantId) { return mapper.selectList(new QueryWrapper<TicketEntity>().eq("tenant_id", tenantId).orderByAsc("first_response_due_at")).stream().map(this::ticket).toList(); }
    @Override public Ticket claim(Long tenantId, Long ticketId, Long membershipId, String idempotencyKey) {
        if (idempotencyKey == null || idempotencyKey.isBlank() || idempotencyKey.length() > 128) {
            throw new IllegalArgumentException("a valid Idempotency-Key is required");
        }
        TicketEntity replay = claimedWith(tenantId, membershipId, idempotencyKey);
        if (replay != null) {
            if (!ticketId.equals(replay.id)) throw new ConflictException("Idempotency-Key was already used for another ticket");
            return ticket(replay);
        }
        TicketEntity source = owned(tenantId, ticketId);
        int updated = mapper.update(new TicketEntity(), new UpdateWrapper<TicketEntity>()
                .eq("id", ticketId).eq("tenant_id", tenantId).eq("version", source.version)
                .isNull("assigned_membership_id")
                .set("assigned_membership_id", membershipId).set("claim_idempotency_key", idempotencyKey)
                .set("status", TicketStatus.OPEN.name()).set("updated_at", Instant.now())
                .setSql("version = version + 1"));
        if (updated != 1) {
            replay = claimedWith(tenantId, membershipId, idempotencyKey);
            if (replay != null && ticketId.equals(replay.id)) return ticket(replay);
            throw new ConflictException("ticket has already been claimed");
        }
        recordAssignment(tenantId, ticketId, null, membershipId, membershipId);
        return ticket(owned(tenantId, ticketId));
    }
    @Override public Ticket assign(Long tenantId, Long ticketId, Long targetMembershipId, Long assignedByMembershipId) {
        TicketEntity source = owned(tenantId, ticketId);
        if (TicketStatus.CLOSED.name().equals(source.status)) throw new IllegalArgumentException("closed ticket cannot be reassigned");
        if (targetMembershipId.equals(source.assignedMembershipId)) return ticket(source);
        int updated = mapper.update(new TicketEntity(), new UpdateWrapper<TicketEntity>()
                .eq("id", ticketId).eq("tenant_id", tenantId).eq("version", source.version)
                .set("assigned_membership_id", targetMembershipId)
                .set("status", TicketStatus.NEW.name().equals(source.status) ? TicketStatus.OPEN.name() : source.status)
                .set("claim_idempotency_key", null).set("updated_at", Instant.now()).setSql("version = version + 1"));
        if (updated != 1) throw new ConflictException("ticket was changed by another agent");
        recordAssignment(tenantId, ticketId, source.assignedMembershipId, targetMembershipId, assignedByMembershipId);
        return ticket(owned(tenantId, ticketId));
    }
    @Override public Ticket changeStatus(Long tenantId, Long ticketId, TicketStatus target) { TicketEntity source = owned(tenantId, ticketId); TicketStatus current = TicketStatus.valueOf(source.status); if (!canTransition(current, target)) throw new IllegalArgumentException("invalid ticket status transition"); int updated = mapper.update(new TicketEntity(), new UpdateWrapper<TicketEntity>().eq("id", ticketId).eq("tenant_id", tenantId).eq("version", source.version).set("status", target.name()).set("updated_at", Instant.now()).setSql("version = version + 1")); if (updated != 1) throw new IllegalArgumentException("ticket was changed by another agent"); return ticket(owned(tenantId, ticketId)); }
    private TicketEntity owned(Long tenantId, Long ticketId) { TicketEntity entity = mapper.selectOne(new QueryWrapper<TicketEntity>().eq("id", ticketId).eq("tenant_id", tenantId)); if (entity == null) throw new IllegalArgumentException("ticket does not belong to tenant"); return entity; }
    private TicketEntity claimedWith(Long tenantId, Long membershipId, String idempotencyKey) { return mapper.selectOne(new QueryWrapper<TicketEntity>().eq("tenant_id", tenantId).eq("assigned_membership_id", membershipId).eq("claim_idempotency_key", idempotencyKey)); }
    private void recordAssignment(Long tenantId, Long ticketId, Long fromMembershipId, Long toMembershipId, Long actorMembershipId) { TicketAssignmentEntity audit = new TicketAssignmentEntity(); audit.tenantId = tenantId; audit.ticketId = ticketId; audit.fromMembershipId = fromMembershipId; audit.toMembershipId = toMembershipId; audit.assignedByMembershipId = actorMembershipId; audit.createdAt = Instant.now(); assignments.insert(audit); }
    private Ticket ticket(TicketEntity entity) { return new Ticket(entity.id, entity.customerId, entity.title, TicketStatus.valueOf(entity.status), TicketPriority.valueOf(entity.priority), entity.assignedMembershipId, entity.firstResponseDueAt, entity.resolutionDueAt); }
    private boolean canTransition(TicketStatus current, TicketStatus target) { return switch (current) { case NEW -> target == TicketStatus.OPEN; case OPEN -> target == TicketStatus.PENDING_CUSTOMER || target == TicketStatus.PENDING_APPROVAL || target == TicketStatus.RESOLVED; case PENDING_CUSTOMER, PENDING_APPROVAL -> target == TicketStatus.OPEN || target == TicketStatus.RESOLVED; case RESOLVED -> target == TicketStatus.OPEN || target == TicketStatus.CLOSED; case CLOSED -> false; }; }
    private Duration firstResponse(TicketPriority priority) { return switch (priority) { case LOW -> Duration.ofHours(8); case NORMAL -> Duration.ofHours(4); case HIGH -> Duration.ofHours(1); case URGENT -> Duration.ofMinutes(15); }; }
    private Duration resolution(TicketPriority priority) { return switch (priority) { case LOW -> Duration.ofHours(72); case NORMAL -> Duration.ofHours(48); case HIGH -> Duration.ofHours(12); case URGENT -> Duration.ofHours(4); }; }
}
