package com.lqq.supportflow.model.infrastructure.persistence;
import com.lqq.supportflow.model.domain.ModelConfig;
import com.lqq.supportflow.model.domain.ModelConfigPort;
import com.lqq.supportflow.model.domain.ModelProtocol;
import java.time.Instant;
import org.springframework.stereotype.Component;
@Component public class MyBatisModelConfigAdapter implements ModelConfigPort {
    private final ModelConfigMapper mapper;
    public MyBatisModelConfigAdapter(ModelConfigMapper mapper) { this.mapper = mapper; }
    public ModelConfig save(Long tenantId, String name, ModelProtocol protocol, String baseUrl, String modelName, String encryptedApiKey, boolean isDefault) {
        Instant now=Instant.now(); ModelConfigEntity entity=new ModelConfigEntity(); entity.tenantId=tenantId; entity.name=name; entity.protocol=protocol.name(); entity.baseUrl=baseUrl; entity.modelName=modelName; entity.encryptedApiKey=encryptedApiKey; entity.isDefault=isDefault; entity.createdAt=now; entity.updatedAt=now; mapper.insert(entity);
        return new ModelConfig(entity.id,name,protocol,baseUrl,modelName,isDefault);
    }
}
