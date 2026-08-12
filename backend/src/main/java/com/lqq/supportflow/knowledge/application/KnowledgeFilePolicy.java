package com.lqq.supportflow.knowledge.application;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import org.springframework.stereotype.Component;

@Component
public class KnowledgeFilePolicy {
    private static final long MAX_UNCOMPRESSED_DOCX_BYTES = 50L * 1024 * 1024;
    private static final Map<String, Set<String>> TYPES = Map.of(
            "pdf", Set.of("application/pdf"),
            "docx", Set.of("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "md", Set.of("text/markdown", "text/plain", "text/x-markdown"),
            "txt", Set.of("text/plain"));

    public String validate(String fileName, String declaredContentType, byte[] content) {
        String extension = extension(fileName);
        String normalizedType = declaredContentType == null ? "" : declaredContentType
                .split(";", 2)[0].trim().toLowerCase(Locale.ROOT);
        if (!TYPES.get(extension).contains(normalizedType)) {
            throw new IllegalArgumentException("document MIME type does not match its extension");
        }
        switch (extension) {
            case "pdf" -> require(content.length >= 5 && startsWith(content, "%PDF-"),
                    "document content is not a PDF");
            case "docx" -> validateDocx(content);
            case "md", "txt" -> require(isText(content), "document content is not valid text");
            default -> throw new IllegalArgumentException("unsupported document extension");
        }
        return normalizedType;
    }

    private String extension(String fileName) {
        if (fileName == null || fileName.isBlank()) throw new IllegalArgumentException("document file name is required");
        String safeName = java.nio.file.Path.of(fileName).getFileName().toString();
        int separator = safeName.lastIndexOf('.');
        if (separator <= 0 || separator == safeName.length() - 1) {
            throw new IllegalArgumentException("supported document extension is required");
        }
        String extension = safeName.substring(separator + 1).toLowerCase(Locale.ROOT);
        if (!TYPES.containsKey(extension)) throw new IllegalArgumentException("unsupported document extension");
        return extension;
    }

    private void validateDocx(byte[] content) {
        require(content.length >= 4 && content[0] == 'P' && content[1] == 'K',
                "document content is not a DOCX archive");
        long uncompressed = 0;
        boolean contentTypes = false;
        boolean documentXml = false;
        try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(content))) {
            ZipEntry entry;
            byte[] buffer = new byte[8192];
            while ((entry = zip.getNextEntry()) != null) {
                String name = entry.getName();
                if (name.startsWith("/") || name.contains("../")) {
                    throw new IllegalArgumentException("DOCX contains an unsafe archive path");
                }
                contentTypes |= "[Content_Types].xml".equals(name);
                documentXml |= "word/document.xml".equals(name);
                int read;
                while ((read = zip.read(buffer)) >= 0) {
                    uncompressed += read;
                    if (uncompressed > MAX_UNCOMPRESSED_DOCX_BYTES) {
                        throw new IllegalArgumentException("DOCX uncompressed content exceeds 50 MB");
                    }
                }
            }
        } catch (IOException exception) {
            throw new IllegalArgumentException("document content is not a readable DOCX", exception);
        }
        require(contentTypes && documentXml, "document content is not a DOCX file");
    }

    private boolean startsWith(byte[] content, String signature) {
        byte[] expected = signature.getBytes(StandardCharsets.US_ASCII);
        for (int index = 0; index < expected.length; index++) if (content[index] != expected[index]) return false;
        return true;
    }

    private boolean isText(byte[] content) {
        for (byte value : content) if (value == 0) return false;
        String decoded = new String(content, StandardCharsets.UTF_8);
        return !decoded.isBlank() && !decoded.contains("\uFFFD");
    }

    private void require(boolean condition, String message) {
        if (!condition) throw new IllegalArgumentException(message);
    }
}
