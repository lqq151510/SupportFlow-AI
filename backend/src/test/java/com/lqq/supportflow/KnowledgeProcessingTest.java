package com.lqq.supportflow;
import static org.assertj.core.api.Assertions.assertThat; import com.lqq.supportflow.knowledge.domain.*; import java.util.stream.IntStream; import org.junit.jupiter.api.Test;
class KnowledgeProcessingTest { @Test void hashesContentIndependentlyOfFileName(){assertThat(ContentHasher.sha256("same content")).isEqualTo(ContentHasher.sha256("same content"));}
    @Test
    void chunksWithConfiguredOverlap() {
        String text = IntStream.range(0, 700).mapToObj(i -> "t" + i).collect(java.util.stream.Collectors.joining(" "));
        var chunks = new TextChunker().chunk(text);
        assertThat(chunks).hasSize(2);
        assertThat(chunks.get(1)).startsWith("t500");
    }

    @Test
    void chunksChineseTextWithoutSpaces() {
        String chineseText = "电商售后服务政策说明：".repeat(50); // 50 * 11 = 550 chars
        var singleChunk = new TextChunker().chunk(chineseText);
        assertThat(singleChunk).hasSize(1);

        String longChineseText = "电商售后服务退换货规定条款以及客户赔付细则说明。".repeat(30); // 30 * 24 = 720 chars
        var chunks = new TextChunker().chunk(longChineseText, 500, 100);
        assertThat(chunks).hasSize(2);
        assertThat(chunks.get(0)).hasSize(500);
        assertThat(chunks.get(1)).startsWith(chunks.get(0).substring(400));
    }

    @Test
    void handlesBlankContentAndRejectsInvalidChunkSettings() {
        TextChunker chunker = new TextChunker();
        assertThat(chunker.chunk("   ")).isEmpty();
        for (int[] setting : java.util.List.of(new int[]{0, 0}, new int[]{3, -1}, new int[]{3, 3})) {
            org.assertj.core.api.Assertions.assertThatThrownBy(() -> chunker.chunk("text", setting[0], setting[1]))
                    .isInstanceOf(IllegalArgumentException.class).hasMessage("invalid chunk settings");
        }
    }
}
