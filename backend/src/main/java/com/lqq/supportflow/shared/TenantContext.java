package com.lqq.supportflow.shared;

import java.util.Optional;

public final class TenantContext {

    private static final ThreadLocal<AuthenticatedPrincipal> CURRENT = new ThreadLocal<>();

    private TenantContext() { }

    public static void set(AuthenticatedPrincipal principal) { CURRENT.set(principal); }

    public static Optional<AuthenticatedPrincipal> current() { return Optional.ofNullable(CURRENT.get()); }

    public static void clear() { CURRENT.remove(); }
}
