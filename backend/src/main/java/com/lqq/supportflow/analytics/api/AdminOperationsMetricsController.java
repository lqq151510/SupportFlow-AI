package com.lqq.supportflow.analytics.api;

import com.lqq.supportflow.analytics.OperationsMetricsService;
import com.lqq.supportflow.analytics.OperationsOverview;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/admin/operations")
public class AdminOperationsMetricsController {
    private final OperationsMetricsService metrics;
    public AdminOperationsMetricsController(OperationsMetricsService metrics) { this.metrics = metrics; }
    @GetMapping("/overview")
    OperationsOverview overview(@AuthenticationPrincipal AuthenticatedPrincipal principal) { return metrics.overview(principal.tenantId()); }
}
