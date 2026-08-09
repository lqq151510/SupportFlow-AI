package com.lqq.supportflow;
import static org.assertj.core.api.Assertions.assertThat; import com.lqq.supportflow.knowledge.domain.*; import java.util.stream.IntStream; import org.junit.jupiter.api.Test;
class KnowledgeProcessingTest { @Test void hashesContentIndependentlyOfFileName(){assertThat(ContentHasher.sha256("same content")).isEqualTo(ContentHasher.sha256("same content"));}
 @Test void chunksWithConfiguredOverlap(){String text=IntStream.range(0,700).mapToObj(i->"t"+i).collect(java.util.stream.Collectors.joining(" "));var chunks=new TextChunker().chunk(text);assertThat(chunks).hasSize(2);assertThat(chunks.get(1)).startsWith("t500");}}
