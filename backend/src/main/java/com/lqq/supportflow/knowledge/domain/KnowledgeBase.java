package com.lqq.supportflow.knowledge.domain;
public record KnowledgeBase(@com.fasterxml.jackson.databind.annotation.JsonSerialize(using=com.fasterxml.jackson.databind.ser.std.ToStringSerializer.class) Long id,String name,String description,String status,long version) { }
