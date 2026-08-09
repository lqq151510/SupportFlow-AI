package com.lqq.supportflow.knowledge.domain;
import java.nio.charset.StandardCharsets; import java.security.MessageDigest; import java.util.HexFormat;
public final class ContentHasher { private ContentHasher(){} public static String sha256(String content){return sha256(content.getBytes(StandardCharsets.UTF_8));} public static String sha256(byte[] content){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));}catch(Exception e){throw new IllegalStateException(e);}}}
