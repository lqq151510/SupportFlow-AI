package com.lqq.supportflow.model.application;
import com.lqq.supportflow.model.domain.ModelConfig;
import com.lqq.supportflow.model.domain.ModelConfigPort;
import com.lqq.supportflow.model.domain.ModelProtocol;
import com.lqq.supportflow.model.domain.ModelSecretPort;
import com.lqq.supportflow.model.domain.ModelUrlPolicy;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
@Service public class CreateModelConfigService {
    private final ModelConfigPort configs; private final ModelSecretPort secrets; private final ModelUrlPolicy urls;
    public CreateModelConfigService(ModelConfigPort configs, ModelSecretPort secrets, ModelUrlPolicy urls) { this.configs=configs; this.secrets=secrets; this.urls=urls; }
    @Transactional public ModelConfig create(Long tenantId,String name,ModelProtocol protocol,String baseUrl,String modelName,String apiKey,boolean isDefault) {
        urls.validate(baseUrl); return configs.save(tenantId,name,protocol,baseUrl,modelName,secrets.encrypt(apiKey),isDefault);
    }
}
