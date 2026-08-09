package com.lqq.supportflow.knowledge.domain;
public enum IngestionStatus { UPLOADED, PARSING, CHUNKING, EMBEDDING, INDEXING, INDEXED, FAILED;
 public boolean canTransitionTo(IngestionStatus target){return switch(this){case UPLOADED->target==PARSING||target==FAILED;case PARSING->target==CHUNKING||target==FAILED;case CHUNKING->target==EMBEDDING||target==FAILED;case EMBEDDING->target==INDEXING||target==FAILED;case INDEXING->target==INDEXED||target==FAILED;case FAILED->target==PARSING;case INDEXED->false;};}}
