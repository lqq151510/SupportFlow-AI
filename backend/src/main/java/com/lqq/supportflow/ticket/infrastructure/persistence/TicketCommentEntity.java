package com.lqq.supportflow.ticket.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("ticket_comments") public class TicketCommentEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public Long ticketId; public Long authorMembershipId; public String content; public Instant createdAt; }
