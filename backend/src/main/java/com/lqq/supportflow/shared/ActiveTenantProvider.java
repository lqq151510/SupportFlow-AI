package com.lqq.supportflow.shared;

import java.util.List;

public interface ActiveTenantProvider {
    List<Long> findActiveTenantIds();
}
