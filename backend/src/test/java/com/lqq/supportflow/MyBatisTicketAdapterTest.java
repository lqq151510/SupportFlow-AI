package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.ticket.domain.TicketPriority;
import com.lqq.supportflow.ticket.domain.TicketStatus;
import com.lqq.supportflow.ticket.infrastructure.persistence.MyBatisTicketAdapter;
import com.lqq.supportflow.ticket.infrastructure.persistence.TicketAssignmentMapper;
import com.lqq.supportflow.ticket.infrastructure.persistence.TicketEntity;
import com.lqq.supportflow.ticket.infrastructure.persistence.TicketMapper;
import java.util.EnumMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class MyBatisTicketAdapterTest {

    @Test
    void assignsTheExpectedSlaForEveryPriority() {
        TicketMapper mapper = mock(TicketMapper.class);
        MyBatisTicketAdapter adapter = new MyBatisTicketAdapter(mapper, mock(TicketAssignmentMapper.class));
        Map<TicketPriority, long[]> expectedMinutes = new EnumMap<>(TicketPriority.class);
        expectedMinutes.put(TicketPriority.LOW, new long[] {480, 4320});
        expectedMinutes.put(TicketPriority.NORMAL, new long[] {240, 2880});
        expectedMinutes.put(TicketPriority.HIGH, new long[] {60, 720});
        expectedMinutes.put(TicketPriority.URGENT, new long[] {15, 240});

        expectedMinutes.forEach((priority, sla) -> {
            adapter.create(7L, 8L, 9L, "order issue", priority);
            ArgumentCaptor<TicketEntity> captor = ArgumentCaptor.forClass(TicketEntity.class);
            org.mockito.Mockito.verify(mapper).insert(captor.capture());
            TicketEntity ticket = captor.getValue();
            assertThat(ticket.firstResponseDueAt.toEpochMilli() - ticket.createdAt.toEpochMilli())
                    .isEqualTo(sla[0] * 60_000);
            assertThat(ticket.resolutionDueAt.toEpochMilli() - ticket.createdAt.toEpochMilli())
                    .isEqualTo(sla[1] * 60_000);
            org.mockito.Mockito.reset(mapper);
        });
    }

    @Test
    void permitsAllValidTicketStatusTransitions() {
        TicketMapper mapper = mock(TicketMapper.class);
        TicketEntity ticket = ticket(TicketStatus.NEW);
        when(mapper.selectOne(any())).thenReturn(ticket);
        when(mapper.update(any(), any())).thenReturn(1);
        MyBatisTicketAdapter adapter = new MyBatisTicketAdapter(mapper, mock(TicketAssignmentMapper.class));

        assertTransition(adapter, ticket, TicketStatus.NEW, TicketStatus.OPEN);
        assertTransition(adapter, ticket, TicketStatus.OPEN, TicketStatus.PENDING_CUSTOMER);
        assertTransition(adapter, ticket, TicketStatus.OPEN, TicketStatus.PENDING_APPROVAL);
        assertTransition(adapter, ticket, TicketStatus.OPEN, TicketStatus.RESOLVED);
        assertTransition(adapter, ticket, TicketStatus.PENDING_CUSTOMER, TicketStatus.OPEN);
        assertTransition(adapter, ticket, TicketStatus.PENDING_APPROVAL, TicketStatus.RESOLVED);
        assertTransition(adapter, ticket, TicketStatus.RESOLVED, TicketStatus.OPEN);
        assertTransition(adapter, ticket, TicketStatus.RESOLVED, TicketStatus.CLOSED);
    }

    @Test
    void rejectsInvalidOrConflictingTransitionsAndForeignTickets() {
        TicketMapper mapper = mock(TicketMapper.class);
        TicketEntity ticket = ticket(TicketStatus.CLOSED);
        when(mapper.selectOne(any())).thenReturn(ticket);
        MyBatisTicketAdapter adapter = new MyBatisTicketAdapter(mapper, mock(TicketAssignmentMapper.class));

        assertThatThrownBy(() -> adapter.changeStatus(7L, 10L, TicketStatus.OPEN))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("invalid ticket status transition");

        ticket.status = TicketStatus.OPEN.name();
        when(mapper.update(any(), any())).thenReturn(0);
        assertThatThrownBy(() -> adapter.changeStatus(7L, 10L, TicketStatus.RESOLVED))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("ticket was changed by another agent");

        when(mapper.selectOne(any())).thenReturn((TicketEntity) null);
        assertThatThrownBy(() -> adapter.claim(7L, 10L, 22L, "claim-1"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("ticket does not belong to tenant");
    }

    @Test
    void replaysTheSameClaimAndRejectsKeyReuseForAnotherTicket() {
        TicketMapper mapper = mock(TicketMapper.class);
        TicketEntity claimed = ticket(TicketStatus.OPEN);
        claimed.assignedMembershipId = 22L;
        claimed.claimIdempotencyKey = "claim-1";
        when(mapper.selectOne(any())).thenReturn(claimed);
        MyBatisTicketAdapter adapter = new MyBatisTicketAdapter(mapper, mock(TicketAssignmentMapper.class));

        assertThat(adapter.claim(7L, 10L, 22L, "claim-1").assignedMembershipId()).isEqualTo(22L);
        assertThatThrownBy(() -> adapter.claim(7L, 11L, 22L, "claim-1"))
                .isInstanceOf(com.lqq.supportflow.shared.ConflictException.class)
                .hasMessage("Idempotency-Key was already used for another ticket");
    }

    private void assertTransition(MyBatisTicketAdapter adapter, TicketEntity ticket, TicketStatus source, TicketStatus target) {
        ticket.status = source.name();
        assertThat(adapter.changeStatus(7L, 10L, target).status()).isEqualTo(source);
    }

    private TicketEntity ticket(TicketStatus status) {
        TicketEntity ticket = new TicketEntity();
        ticket.id = 10L;
        ticket.tenantId = 7L;
        ticket.customerId = 8L;
        ticket.title = "order issue";
        ticket.status = status.name();
        ticket.priority = TicketPriority.NORMAL.name();
        ticket.version = 0L;
        ticket.firstResponseDueAt = java.time.Instant.now();
        ticket.resolutionDueAt = java.time.Instant.now();
        return ticket;
    }
}
