package com.lqq.supportflow.ticket.infrastructure.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;

@TableName("ticket_assignments")
public class TicketAssignmentEntity {
    @TableId(type = IdType.ASSIGN_ID) public Long id;
    public Long tenantId;
    public Long ticketId;
    public Long fromMembershipId;
    public Long toMembershipId;
    public Long assignedByMembershipId;
    public Instant createdAt;
}
