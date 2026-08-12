package com.lqq.supportflow.model.infrastructure.security;

import java.net.URI;
import com.lqq.supportflow.model.domain.ModelUrlPolicy;
import org.springframework.stereotype.Component;

@Component
public class ModelBaseUrlValidator implements ModelUrlPolicy {

    public void validate(String value) {
        URI uri = URI.create(value);
        String host = uri.getHost();
        if (!"https".equalsIgnoreCase(uri.getScheme()) || host == null || isPrivate(host)) {
            throw new IllegalArgumentException("model base URL must be a public HTTPS URL");
        }
    }

    private boolean isPrivate(String host) {
        return host.equalsIgnoreCase("localhost") || host.equals("::1") || host.equals("[::1]") || host.startsWith("127.")
                || host.startsWith("10.") || host.startsWith("192.168.") || host.matches("172\\.(1[6-9]|2[0-9]|3[0-1])\\..*");
    }
}
