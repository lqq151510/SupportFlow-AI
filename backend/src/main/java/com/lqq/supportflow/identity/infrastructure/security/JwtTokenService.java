package com.lqq.supportflow.identity.infrastructure.security;

import com.lqq.supportflow.identity.domain.IssuedToken;
import com.lqq.supportflow.identity.domain.TokenIssuer;
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
public class JwtTokenService implements TokenIssuer {
    private final JwtProperties properties; private final Clock clock; private final SecretKey key;
    public JwtTokenService(JwtProperties properties) {
        this.properties = properties; this.clock = Clock.systemUTC(); this.key = Keys.hmacShaKeyFor(Base64.getDecoder().decode(properties.secretBase64()));
    }
    @Override
    public IssuedToken issueAccessToken(Long userId, Long tenantId, Long membershipId, String role) {
        return issue("access", userId, tenantId, membershipId, role, properties.accessTokenTtl());
    }

    @Override
    public IssuedToken issueRefreshToken(Long userId, Long tenantId, Long membershipId, String role) {
        return issue("refresh", userId, tenantId, membershipId, role, properties.refreshTokenTtl());
    }

    public Claims parse(String token) { return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload(); }
    public String jti(String token) { return parse(token).getId(); }

    private IssuedToken issue(String tokenType, Long userId, Long tenantId, Long membershipId, String role, java.time.Duration ttl) {
        Instant now = clock.instant();
        Instant expiresAt = now.plus(ttl);
        String jti = UUID.randomUUID().toString();
        String value = Jwts.builder().subject(userId.toString()).id(jti).claim("tokenType", tokenType)
                .claim("tenantId", tenantId.toString()).claim("membershipId", membershipId.toString()).claim("role", role)
                .issuedAt(Date.from(now)).expiration(Date.from(expiresAt)).signWith(key).compact();
        return new IssuedToken(value, jti, expiresAt);
    }
}
