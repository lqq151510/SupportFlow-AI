package com.lqq.supportflow.conversation.domain;
import java.util.List;
public interface GenerationEventStore { void append(Long generationId,String type,String data); void appendIfAbsent(Long generationId,String type,String data); List<GenerationEvent> readAfter(Long generationId,String lastEventId); }
