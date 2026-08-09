package com.lqq.supportflow.identity.infrastructure.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;

@TableName("refresh_tokens")
public class RefreshTokenEntity {
    @TableId(type = IdType.ASSIGN_ID) public Long id;
    public Long userId; public Long tenantId; public String jti; public String tokenHash; public Instant expiresAt; public Instant revokedAt; public Instant createdAt;
}
