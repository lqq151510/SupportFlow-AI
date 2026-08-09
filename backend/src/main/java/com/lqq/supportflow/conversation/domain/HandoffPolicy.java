package com.lqq.supportflow.conversation.domain;
import java.util.Locale; import org.springframework.stereotype.Component;
@Component public class HandoffPolicy { public boolean requiresHandoff(String content){String normalized=content.toLowerCase(Locale.ROOT);return normalized.contains("人工")||normalized.contains("human")||normalized.contains("投诉")||normalized.contains("威胁")||normalized.contains("refund")||normalized.contains("退款")||normalized.contains("compensation")||normalized.contains("补偿");}}
