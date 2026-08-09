package com.lqq.supportflow.conversation.domain;
import java.util.List;
public interface GenerationEventStore { void append(Long tenantId,Long generationId,String type,String data); void appendIfAbsent(Long tenantId,Long generationId,String type,String data); List<GenerationEvent> readAfter(Long tenantId,Long generationId,String lastEventId); }
