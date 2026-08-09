package com.lqq.supportflow.model;
import com.lqq.supportflow.model.domain.*; import java.util.List; import org.springframework.stereotype.Service;
@Service public class ModelEmbeddingService { private final EmbeddingGateway gateway; public ModelEmbeddingService(EmbeddingGateway gateway){this.gateway=gateway;} public List<float[]> embed(Long tenantId,List<String> inputs){return gateway.embedBatch(new EmbeddingRequest(tenantId,inputs));}}
