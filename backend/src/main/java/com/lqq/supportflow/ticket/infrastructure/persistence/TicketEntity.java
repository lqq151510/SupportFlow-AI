package com.lqq.supportflow.ticket.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("tickets") public class TicketEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public Long customerId; public Long conversationId; public String title; public String status; public String priority; public Long assignedMembershipId; public Instant firstResponseDueAt; public Instant resolutionDueAt; @Version public Long version; public Instant createdAt; public Instant updatedAt; }
