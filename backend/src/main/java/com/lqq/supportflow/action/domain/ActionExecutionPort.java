package com.lqq.supportflow.action.domain;
public interface ActionExecutionPort { void executeOnce(Long tenantId,Long approvalId,String actionType); }
