package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.lqq.supportflow.knowledge.application.KnowledgeFilePolicy;
import com.lqq.supportflow.knowledge.infrastructure.extraction.TikaDocumentTextExtractor;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.junit.jupiter.api.Test;

class KnowledgeDocumentFormatTest {
    private final KnowledgeFilePolicy policy = new KnowledgeFilePolicy();
    private final TikaDocumentTextExtractor extractor = new TikaDocumentTextExtractor();

    @Test
    void acceptsAndExtractsPdfDocxMarkdownAndPlainText() throws Exception {
        assertFormat("refund.pdf", "application/pdf", pdf("PDF refund policy"), "PDF refund policy");
        assertFormat("refund.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                docx("DOCX refund policy"), "DOCX refund policy");
        assertFormat("refund.md", "text/markdown", "# Markdown refund policy".getBytes(StandardCharsets.UTF_8),
                "Markdown refund policy");
        assertFormat("refund.txt", "text/plain", "Plain refund policy".getBytes(StandardCharsets.UTF_8),
                "Plain refund policy");
    }

    @Test
    void rejectsExtensionMimeAndSignatureMismatches() {
        byte[] text = "not a PDF".getBytes(StandardCharsets.UTF_8);
        assertThatThrownBy(() -> policy.validate("refund.exe", "application/octet-stream", text))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("unsupported document extension");
        assertThatThrownBy(() -> policy.validate("refund.pdf", "text/plain", text))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("document MIME type does not match its extension");
        assertThatThrownBy(() -> policy.validate("refund.pdf", "application/pdf", text))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("document content is not a PDF");
    }

    private void assertFormat(String name, String contentType, byte[] bytes, String expectedText) {
        assertThat(policy.validate(name, contentType, bytes)).isEqualTo(contentType);
        assertThat(extractor.extract(new ByteArrayInputStream(bytes), contentType)).contains(expectedText);
    }

    private byte[] pdf(String text) throws Exception {
        try (PDDocument document = new PDDocument(); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            PDPage page = new PDPage();
            document.addPage(page);
            try (PDPageContentStream content = new PDPageContentStream(document, page)) {
                content.beginText();
                content.setFont(new PDType1Font(Standard14Fonts.FontName.HELVETICA), 12);
                content.newLineAtOffset(72, 720);
                content.showText(text);
                content.endText();
            }
            document.save(output);
            return output.toByteArray();
        }
    }

    private byte[] docx(String text) throws Exception {
        try (XWPFDocument document = new XWPFDocument(); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            document.createParagraph().createRun().setText(text);
            document.write(output);
            return output.toByteArray();
        }
    }
}
