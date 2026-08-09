package com.lqq.supportflow.identity.domain;

public interface TokenIssuer {

    IssuedToken issueAccessToken(Long userId, Long tenantId, Long membershipId, String role);

    IssuedToken issueRefreshToken(Long userId, Long tenantId, Long membershipId, String role);
}
