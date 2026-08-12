package com.lqq.supportflow.model.infrastructure.persistence;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.lqq.supportflow.model.domain.*;
import java.time.Instant;
import org.springframework.stereotype.Component;
@Component public class MyBatisModelConfigAdapter implements ModelConfigPort {
    private final ModelConfigMapper mapper;
    public MyBatisModelConfigAdapter(ModelConfigMapper mapper) { this.mapper = mapper; }
    public ModelConfig save(Long tenantId, String name, ModelProtocol protocol, String baseUrl, String modelName, String encryptedApiKey, boolean isDefault) {
        Instant now=Instant.now(); if(isDefault) mapper.update(new ModelConfigEntity(),new com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper<ModelConfigEntity>().eq("tenant_id",tenantId).set("is_default",false).set("updated_at",now)); ModelConfigEntity entity=new ModelConfigEntity(); entity.tenantId=tenantId; entity.name=name; entity.protocol=protocol.name(); entity.baseUrl=baseUrl; entity.modelName=modelName; entity.encryptedApiKey=encryptedApiKey; entity.isDefault=isDefault; entity.createdAt=now; entity.updatedAt=now; mapper.insert(entity);
        return new ModelConfig(entity.id,name,protocol,baseUrl,modelName,isDefault);
    }
    public java.util.List<ModelConfig> list(Long tenantId) { return mapper.selectList(new QueryWrapper<ModelConfigEntity>().eq("tenant_id",tenantId).orderByDesc("is_default").orderByAsc("created_at")).stream().map(entity->new ModelConfig(entity.id,entity.name,ModelProtocol.valueOf(entity.protocol),entity.baseUrl,entity.modelName,Boolean.TRUE.equals(entity.isDefault))).toList(); }
    public java.util.Optional<EmbeddingModelConfig> findDefaultEmbedding(Long tenantId) { return java.util.Optional.ofNullable(mapper.selectOne(new QueryWrapper<ModelConfigEntity>().eq("tenant_id",tenantId).eq("protocol",ModelProtocol.OPENAI_COMPATIBLE.name()).eq("is_default",true))).map(entity->new EmbeddingModelConfig(entity.baseUrl,entity.modelName,entity.encryptedApiKey)); }
    public java.util.Optional<ChatModelConfig> findDefaultChat(Long tenantId) { return java.util.Optional.ofNullable(mapper.selectOne(new QueryWrapper<ModelConfigEntity>().eq("tenant_id",tenantId).eq("is_default",true))).map(entity->new ChatModelConfig(ModelProtocol.valueOf(entity.protocol),entity.baseUrl,entity.modelName,entity.encryptedApiKey)); }
}
