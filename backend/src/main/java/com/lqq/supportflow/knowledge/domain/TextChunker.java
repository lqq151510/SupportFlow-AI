package com.lqq.supportflow.knowledge.domain;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class TextChunker {
    public static final int DEFAULT_SIZE = 600, DEFAULT_OVERLAP = 100;

    public List<String> chunk(String content) {
        return chunk(content, DEFAULT_SIZE, DEFAULT_OVERLAP);
    }

    public List<String> chunk(String content, int size, int overlap) {
        if (size <= 0 || overlap < 0 || overlap >= size) {
            throw new IllegalArgumentException("invalid chunk settings");
        }
        if (content == null || content.isBlank()) {
            return List.of();
        }
        String trimmed = content.trim();
        String[] tokens = trimmed.split("\\s+");
        if (tokens.length > 1 && tokens.length >= size) {
            List<String> result = new ArrayList<>();
            for (int start = 0; start < tokens.length; start += size - overlap) {
                int end = Math.min(start + size, tokens.length);
                result.add(String.join(" ", Arrays.copyOfRange(tokens, start, end)));
                if (end == tokens.length) break;
            }
            return result;
        }

        if (trimmed.length() > size) {
            List<String> result = new ArrayList<>();
            int step = size - overlap;
            for (int start = 0; start < trimmed.length(); start += step) {
                int end = Math.min(start + size, trimmed.length());
                result.add(trimmed.substring(start, end));
                if (end == trimmed.length()) break;
            }
            return result;
        }

        return List.of(trimmed);
    }
}
