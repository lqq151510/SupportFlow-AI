package com.lqq.supportflow.model.infrastructure.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;

@TableName("model_configs") public class ModelConfigEntity {
    @TableId(type = IdType.ASSIGN_ID) public Long id;
    public Long tenantId; public String name; public String protocol; public String baseUrl; public String modelName;
    public String encryptedApiKey; public Boolean isDefault; public Instant createdAt; public Instant updatedAt;
}
