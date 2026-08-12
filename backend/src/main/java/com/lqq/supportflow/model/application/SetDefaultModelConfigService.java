package com.lqq.supportflow.model.application;

import com.lqq.supportflow.model.domain.ModelConfig;
import com.lqq.supportflow.model.domain.ModelConfigPort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class SetDefaultModelConfigService {
    private final ModelConfigPort configs;

    public SetDefaultModelConfigService(ModelConfigPort configs) { this.configs = configs; }

    @Transactional
    public ModelConfig setDefault(Long tenantId, Long modelConfigId) {
        return configs.setDefault(tenantId, modelConfigId);
    }
}
