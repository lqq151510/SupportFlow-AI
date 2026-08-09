package com.lqq.supportflow.identity.infrastructure.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.time.Clock;
import java.time.Instant;
import java.util.Base64;
import java.util.Date;
import java.util.UUID;
import javax.crypto.SecretKey;
import org.springframework.stereotype.Component;

@Component
public class JwtTokenService {
    private final JwtProperties properties; private final Clock clock; private final SecretKey key;
    public JwtTokenService(JwtProperties properties) {
        this.properties = properties; this.clock = Clock.systemUTC(); this.key = Keys.hmacShaKeyFor(Base64.getDecoder().decode(properties.secretBase64()));
    }
    public String issueAccessToken(Long userId, Long tenantId, Long membershipId, String role) {
        return issue("access", userId, tenantId, membershipId, role, properties.accessTokenTtl());
    }
    public String issueRefreshToken(Long userId, Long tenantId, Long membershipId, String role) {
        return issue("refresh", userId, tenantId, membershipId, role, properties.refreshTokenTtl());
    }
    public Claims parse(String token) { return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload(); }
    private String issue(String tokenType, Long userId, Long tenantId, Long membershipId, String role, java.time.Duration ttl) {
        Instant now = clock.instant();
        return Jwts.builder().subject(userId.toString()).id(UUID.randomUUID().toString()).claim("tokenType", tokenType)
                .claim("tenantId", tenantId.toString()).claim("membershipId", membershipId.toString()).claim("role", role)
                .issuedAt(Date.from(now)).expiration(Date.from(now.plus(ttl))).signWith(key).compact();
    }
}
