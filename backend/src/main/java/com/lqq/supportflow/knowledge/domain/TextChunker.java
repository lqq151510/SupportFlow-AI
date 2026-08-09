package com.lqq.supportflow.knowledge.domain;
import java.util.ArrayList; import java.util.List;
public class TextChunker { public static final int DEFAULT_SIZE=600, DEFAULT_OVERLAP=100;
 public List<String> chunk(String content){return chunk(content,DEFAULT_SIZE,DEFAULT_OVERLAP);}
 public List<String> chunk(String content,int size,int overlap){if(size<=0||overlap<0||overlap>=size)throw new IllegalArgumentException("invalid chunk settings");String[] tokens=content.trim().split("\\s+");if(content.isBlank())return List.of();List<String> result=new ArrayList<>();for(int start=0;start<tokens.length;start+=size-overlap){int end=Math.min(start+size,tokens.length);result.add(String.join(" ",java.util.Arrays.copyOfRange(tokens,start,end)));if(end==tokens.length)break;}return result;}}
