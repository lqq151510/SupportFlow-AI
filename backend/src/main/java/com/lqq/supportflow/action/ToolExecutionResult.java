package com.lqq.supportflow.action;

import java.util.Map;

public record ToolExecutionResult(String toolName, String status, Map<String, Object> data) { }
