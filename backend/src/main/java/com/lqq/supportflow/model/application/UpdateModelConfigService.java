package com.lqq.supportflow.model.application;

import com.lqq.supportflow.model.domain.ModelConfig;
import com.lqq.supportflow.model.domain.ModelConfigPort;
import com.lqq.supportflow.model.domain.ModelProtocol;
import com.lqq.supportflow.model.domain.ModelSecretPort;
import com.lqq.supportflow.model.domain.ModelUrlPolicy;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class UpdateModelConfigService {

    private final ModelConfigPort configs;
    private final ModelSecretPort secrets;
    private final ModelUrlPolicy urls;

    public UpdateModelConfigService(ModelConfigPort configs, ModelSecretPort secrets, ModelUrlPolicy urls) {
        this.configs = configs;
        this.secrets = secrets;
        this.urls = urls;
    }

    @Transactional
    public ModelConfig update(Long tenantId, Long modelConfigId, String name, ModelProtocol protocol,
                              String baseUrl, String modelName, String apiKey,
                              Boolean isDefault, Boolean isKnowledgeDefault) {
        if (baseUrl != null && !baseUrl.isBlank()) {
            urls.validate(baseUrl);
        }
        String encryptedKey = (apiKey != null && !apiKey.isBlank()) ? secrets.encrypt(apiKey) : null;
        return configs.update(tenantId, modelConfigId, name, protocol, baseUrl, modelName, encryptedKey, isDefault, isKnowledgeDefault);
    }
}
