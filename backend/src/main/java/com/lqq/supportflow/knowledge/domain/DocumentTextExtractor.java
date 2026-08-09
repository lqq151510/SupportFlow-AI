package com.lqq.supportflow.knowledge.domain;
import java.io.InputStream;
public interface DocumentTextExtractor { String extract(InputStream content,String contentType); }
