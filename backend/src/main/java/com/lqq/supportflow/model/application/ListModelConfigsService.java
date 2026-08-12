package com.lqq.supportflow.model.application;

import com.lqq.supportflow.model.domain.ModelConfig;
import com.lqq.supportflow.model.domain.ModelConfigPort;
import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class ListModelConfigsService {
    private final ModelConfigPort configs;

    public ListModelConfigsService(ModelConfigPort configs) {
        this.configs = configs;
    }

    public List<ModelConfig> list(Long tenantId) {
        return configs.list(tenantId);
    }
}
