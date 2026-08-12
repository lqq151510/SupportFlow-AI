package com.lqq.supportflow.action.infrastructure.persistence;

import com.lqq.supportflow.action.domain.ActionExecutionPort;
import java.time.Instant;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Component;

@Component
public class MyBatisActionExecutionAdapter implements ActionExecutionPort {
    private final ActionExecutionMapper mapper;

    public MyBatisActionExecutionAdapter(ActionExecutionMapper mapper) { this.mapper = mapper; }

    @Override
    public boolean executeOnce(Long tenantId, Long approvalId, String actionType,
                               long executionVersion, String businessIdempotencyKey) {
        ActionExecutionEntity entity = new ActionExecutionEntity();
        entity.tenantId = tenantId;
        entity.approvalId = approvalId;
        entity.actionType = actionType;
        entity.executionVersion = executionVersion;
        entity.businessIdempotencyKey = businessIdempotencyKey;
        entity.status = "EXECUTED";
        entity.executedAt = Instant.now();
        try {
            mapper.insert(entity);
            return true;
        } catch (DuplicateKeyException ignored) {
            return false;
        }
    }
}
