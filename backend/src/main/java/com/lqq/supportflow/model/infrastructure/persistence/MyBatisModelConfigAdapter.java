package com.lqq.supportflow.model.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.lqq.supportflow.model.domain.*;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import org.springframework.stereotype.Component;

@Component
public class MyBatisModelConfigAdapter implements ModelConfigPort {

    private final ModelConfigMapper mapper;

    public MyBatisModelConfigAdapter(ModelConfigMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public ModelConfig save(Long tenantId, String name, ModelProtocol protocol, String baseUrl,
                            String modelName, String encryptedApiKey, boolean isDefault, boolean isKnowledgeDefault) {
        Instant now = Instant.now();
        if (isDefault) {
            mapper.update(new ModelConfigEntity(), new UpdateWrapper<ModelConfigEntity>()
                    .eq("tenant_id", tenantId).set("is_default", false).set("updated_at", now));
        }
        if (isKnowledgeDefault) {
            mapper.update(new ModelConfigEntity(), new UpdateWrapper<ModelConfigEntity>()
                    .eq("tenant_id", tenantId).set("is_knowledge_default", false).set("updated_at", now));
        }
        ModelConfigEntity entity = new ModelConfigEntity();
        entity.tenantId = tenantId;
        entity.name = name;
        entity.protocol = protocol.name();
        entity.baseUrl = baseUrl;
        entity.modelName = modelName;
        entity.encryptedApiKey = encryptedApiKey;
        entity.isDefault = isDefault;
        entity.isKnowledgeDefault = isKnowledgeDefault;
        entity.createdAt = now;
        entity.updatedAt = now;
        mapper.insert(entity);

        return toModelConfig(entity);
    }

    @Override
    public ModelConfig update(Long tenantId, Long modelConfigId, String name, ModelProtocol protocol,
                             String baseUrl, String modelName, String encryptedApiKeyOrNull,
                             Boolean isDefault, Boolean isKnowledgeDefault) {
        ModelConfigEntity target = mapper.selectOne(new QueryWrapper<ModelConfigEntity>()
                .eq("id", modelConfigId).eq("tenant_id", tenantId));
        if (target == null) {
            throw new IllegalArgumentException("model configuration does not belong to tenant");
        }

        Instant now = Instant.now();
        UpdateWrapper<ModelConfigEntity> updateWrapper = new UpdateWrapper<ModelConfigEntity>()
                .eq("id", modelConfigId).eq("tenant_id", tenantId);

        if (name != null && !name.isBlank()) {
            target.name = name.trim();
            updateWrapper.set("name", target.name);
        }
        if (protocol != null) {
            target.protocol = protocol.name();
            updateWrapper.set("protocol", target.protocol);
        }
        if (baseUrl != null && !baseUrl.isBlank()) {
            target.baseUrl = baseUrl.trim();
            updateWrapper.set("base_url", target.baseUrl);
        }
        if (modelName != null && !modelName.isBlank()) {
            target.modelName = modelName.trim();
            updateWrapper.set("model_name", target.modelName);
        }
        if (encryptedApiKeyOrNull != null && !encryptedApiKeyOrNull.isBlank()) {
            target.encryptedApiKey = encryptedApiKeyOrNull;
            updateWrapper.set("encrypted_api_key", target.encryptedApiKey);
        }
        if (isDefault != null) {
            if (isDefault) {
                mapper.update(new ModelConfigEntity(), new UpdateWrapper<ModelConfigEntity>()
                        .eq("tenant_id", tenantId).set("is_default", false).set("updated_at", now));
            }
            target.isDefault = isDefault;
            updateWrapper.set("is_default", isDefault);
        }
        if (isKnowledgeDefault != null) {
            if (isKnowledgeDefault) {
                mapper.update(new ModelConfigEntity(), new UpdateWrapper<ModelConfigEntity>()
                        .eq("tenant_id", tenantId).set("is_knowledge_default", false).set("updated_at", now));
            }
            target.isKnowledgeDefault = isKnowledgeDefault;
            updateWrapper.set("is_knowledge_default", isKnowledgeDefault);
        }

        updateWrapper.set("updated_at", now);
        mapper.update(new ModelConfigEntity(), updateWrapper);

        return toModelConfig(target);
    }

    @Override
    public ModelConfig setDefault(Long tenantId, Long modelConfigId) {
        ModelConfigEntity target = mapper.selectOne(new QueryWrapper<ModelConfigEntity>()
                .eq("id", modelConfigId).eq("tenant_id", tenantId));
        if (target == null) throw new IllegalArgumentException("model configuration does not belong to tenant");

        Instant now = Instant.now();
        mapper.update(new ModelConfigEntity(), new UpdateWrapper<ModelConfigEntity>()
                .eq("tenant_id", tenantId).set("is_default", false).set("updated_at", now));
        mapper.update(new ModelConfigEntity(), new UpdateWrapper<ModelConfigEntity>()
                .eq("id", modelConfigId).eq("tenant_id", tenantId).set("is_default", true).set("updated_at", now));
        target.isDefault = true;
        return toModelConfig(target);
    }

    @Override
    public ModelConfig setKnowledgeDefault(Long tenantId, Long modelConfigId) {
        ModelConfigEntity target = mapper.selectOne(new QueryWrapper<ModelConfigEntity>()
                .eq("id", modelConfigId).eq("tenant_id", tenantId));
        if (target == null) throw new IllegalArgumentException("model configuration does not belong to tenant");

        Instant now = Instant.now();
        mapper.update(new ModelConfigEntity(), new UpdateWrapper<ModelConfigEntity>()
                .eq("tenant_id", tenantId).set("is_knowledge_default", false).set("updated_at", now));
        mapper.update(new ModelConfigEntity(), new UpdateWrapper<ModelConfigEntity>()
                .eq("id", modelConfigId).eq("tenant_id", tenantId).set("is_knowledge_default", true).set("updated_at", now));
        target.isKnowledgeDefault = true;
        return toModelConfig(target);
    }

    @Override
    public List<ModelConfig> list(Long tenantId) {
        return mapper.selectList(new QueryWrapper<ModelConfigEntity>()
                        .eq("tenant_id", tenantId)
                        .orderByDesc("is_default")
                        .orderByDesc("is_knowledge_default")
                        .orderByAsc("created_at"))
                .stream().map(this::toModelConfig).toList();
    }

    @Override
    public Optional<EmbeddingModelConfig> findDefaultEmbedding(Long tenantId) {
        return Optional.ofNullable(mapper.selectOne(new QueryWrapper<ModelConfigEntity>()
                        .eq("tenant_id", tenantId)
                        .eq("protocol", ModelProtocol.OPENAI_COMPATIBLE.name())
                        .eq("is_default", true)))
                .map(entity -> new EmbeddingModelConfig(entity.baseUrl, entity.modelName, entity.encryptedApiKey));
    }

    @Override
    public Optional<ChatModelConfig> findDefaultChat(Long tenantId) {
        return Optional.ofNullable(mapper.selectOne(new QueryWrapper<ModelConfigEntity>()
                        .eq("tenant_id", tenantId)
                        .eq("is_default", true)))
                .map(entity -> new ChatModelConfig(ModelProtocol.valueOf(entity.protocol), entity.baseUrl, entity.modelName, entity.encryptedApiKey));
    }

    @Override
    public Optional<ChatModelConfig> findDefaultKnowledge(Long tenantId) {
        ModelConfigEntity entity = mapper.selectOne(new QueryWrapper<ModelConfigEntity>()
                .eq("tenant_id", tenantId)
                .eq("is_knowledge_default", true));
        if (entity == null) {
            entity = mapper.selectOne(new QueryWrapper<ModelConfigEntity>()
                    .eq("tenant_id", tenantId)
                    .eq("is_default", true));
        }
        return Optional.ofNullable(entity)
                .map(e -> new ChatModelConfig(ModelProtocol.valueOf(e.protocol), e.baseUrl, e.modelName, e.encryptedApiKey));
    }

    private ModelConfig toModelConfig(ModelConfigEntity entity) {
        return new ModelConfig(
                entity.id,
                entity.name,
                ModelProtocol.valueOf(entity.protocol),
                entity.baseUrl,
                entity.modelName,
                Boolean.TRUE.equals(entity.isDefault),
                Boolean.TRUE.equals(entity.isKnowledgeDefault)
        );
    }
}
