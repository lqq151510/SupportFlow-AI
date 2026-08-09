package com.lqq.supportflow.ticket.infrastructure.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;

@TableName("ticket_sla_alerts")
public class TicketSlaAlertEntity {
    @TableId(type = IdType.ASSIGN_ID) public Long id;
    public Long tenantId;
    public Long ticketId;
    public String alertType;
    public Instant dueAt;
    public Instant alertedAt;
}
