package com.lqq.supportflow.conversation.infrastructure.events;

import com.lqq.supportflow.conversation.domain.GenerationEvent;
import com.lqq.supportflow.conversation.domain.GenerationEventStore;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.domain.Range;
import org.springframework.data.redis.connection.stream.MapRecord;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.connection.stream.StreamRecords;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "supportflow.generation.redis", name = "enabled", havingValue = "true")
public class RedisGenerationEventStore implements GenerationEventStore {

    private final StringRedisTemplate redis;
    private final Duration ttl;

    public RedisGenerationEventStore(StringRedisTemplate redis,
            @Value("${supportflow.generation.redis.ttl:PT10M}") Duration ttl) {
        this.redis = redis;
        this.ttl = ttl;
    }

    @Override
    public void append(Long tenantId, Long generationId, String type, String data) {
        String key = streamKey(tenantId, generationId);
        redis.opsForStream().add(StreamRecords.newRecord().in(key).ofMap(Map.of("type", type, "data", data)));
        redis.expire(key, ttl);
    }

    @Override
    public void appendIfAbsent(Long tenantId, Long generationId, String type, String data) {
        String marker = streamKey(tenantId, generationId) + ":once:" + type;
        Boolean claimed = redis.opsForValue().setIfAbsent(marker, "1", ttl);
        if (Boolean.TRUE.equals(claimed)) append(tenantId, generationId, type, data);
    }

    @Override
    public List<GenerationEvent> readAfter(Long tenantId, Long generationId, String lastEventId) {
        return redis.opsForStream().range(streamKey(tenantId, generationId), Range.unbounded()).stream()
                .filter(record -> lastEventId == null || lastEventId.isBlank()
                        || compareRecordIds(record.getId().getValue(), lastEventId) > 0)
                .map(record -> new GenerationEvent(record.getId().getValue(),
                        String.valueOf(record.getValue().get("type")),
                        String.valueOf(record.getValue().get("data"))))
                .toList();
    }

    private String streamKey(Long tenantId, Long generationId) { return "supportflow:tenant:" + tenantId + ":generation:" + generationId + ":events"; }

    private int compareRecordIds(String left, String right) {
        String[] a = left.split("-", 2); String[] b = right.split("-", 2);
        int timestamp = Long.compare(Long.parseLong(a[0]), Long.parseLong(b[0]));
        return timestamp != 0 ? timestamp : Long.compare(Long.parseLong(a[1]), Long.parseLong(b[1]));
    }
}
