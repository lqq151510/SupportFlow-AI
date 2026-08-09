package com.lqq.supportflow.model.domain;

public sealed interface ModelEvent permits ModelEvent.TextDelta, ModelEvent.ToolCallStarted,
        ModelEvent.ToolCallArgumentsDelta, ModelEvent.ToolCallCompleted, ModelEvent.UsageReported,
        ModelEvent.ModelCompleted, ModelEvent.ModelFailed {

    record TextDelta(String text) implements ModelEvent { }
    record ToolCallStarted(String callId, String name) implements ModelEvent { }
    record ToolCallArgumentsDelta(String callId, String argumentsDelta) implements ModelEvent { }
    record ToolCallCompleted(String callId) implements ModelEvent { }
    record UsageReported(int inputTokens, int outputTokens) implements ModelEvent { }
    record ModelCompleted() implements ModelEvent { }
    record ModelFailed(String code, String message) implements ModelEvent { }
}
