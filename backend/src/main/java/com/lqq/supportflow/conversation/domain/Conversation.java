package com.lqq.supportflow.conversation.domain;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;

public record Conversation(@JsonSerialize(using = ToStringSerializer.class) Long id, ConversationStatus status) { }
