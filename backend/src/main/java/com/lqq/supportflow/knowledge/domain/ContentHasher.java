package com.lqq.supportflow.knowledge.domain;
import java.nio.charset.StandardCharsets; import java.security.MessageDigest; import java.util.HexFormat;
public final class ContentHasher { private ContentHasher(){} public static String sha256(String content){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content.getBytes(StandardCharsets.UTF_8)));}catch(Exception e){throw new IllegalStateException(e);}}}
