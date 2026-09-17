package com.lqq.supportflow.model.api;

import com.lqq.supportflow.model.ModelUsageService;
import com.lqq.supportflow.model.application.*;
import com.lqq.supportflow.model.domain.ModelConfig;
import com.lqq.supportflow.model.domain.ModelUsagePort;
import com.lqq.supportflow.model.domain.ModelUsageRecord;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/admin/models")
public class AdminModelConfigController {

    private final CreateModelConfigService service;
    private final UpdateModelConfigService updateService;
    private final ProbeModelConnectionService probe;
    private final ListModelConfigsService list;
    private final SetDefaultModelConfigService defaults;
    private final ModelUsageService usageService;

    public AdminModelConfigController(
            CreateModelConfigService service,
            UpdateModelConfigService updateService,
            ProbeModelConnectionService probe,
            ListModelConfigsService list,
            SetDefaultModelConfigService defaults,
            ModelUsageService usageService) {
        this.service = service;
        this.updateService = updateService;
        this.probe = probe;
        this.list = list;
        this.defaults = defaults;
        this.usageService = usageService;
    }

    @GetMapping
    public List<ModelConfig> list(@AuthenticationPrincipal AuthenticatedPrincipal principal) {
        return list.list(principal.tenantId());
    }

    @PostMapping
    public ResponseEntity<ModelConfig> create(
            @AuthenticationPrincipal AuthenticatedPrincipal principal,
            @Valid @RequestBody CreateModelConfigRequest request) {
        ModelConfig result = service.create(principal.tenantId(), request.name(), request.protocol(),
                request.baseUrl(), request.modelName(), request.apiKey(), request.isDefault(), request.isKnowledgeDefault());
        return ResponseEntity.created(URI.create("/api/v1/admin/models/" + result.id())).body(result);
    }

    @PutMapping("/{modelConfigId}")
    public ModelConfig update(
            @AuthenticationPrincipal AuthenticatedPrincipal principal,
            @PathVariable Long modelConfigId,
            @Valid @RequestBody UpdateModelConfigRequest request) {
        return updateService.update(principal.tenantId(), modelConfigId, request.name(), request.protocol(),
                request.baseUrl(), request.modelName(), request.apiKey(), request.isDefault(), request.isKnowledgeDefault());
    }

    @PostMapping("/probe")
    public ProbeModelConnectionService.ProbeResult probe(
            @AuthenticationPrincipal AuthenticatedPrincipal principal,
            @Valid @RequestBody ModelProbeRequest request) {
        ProbeModelConnectionService.ProbeResult result = probe.probe(request.baseUrl(), request.apiKey());
        if (principal != null) {
            usageService.recordUsage(principal.tenantId(), "PROBE", "probe-check", "HTTP", 10, 10, 100);
        }
        return result;
    }

    @PatchMapping("/{modelConfigId}/default")
    public ModelConfig setDefault(
            @AuthenticationPrincipal AuthenticatedPrincipal principal,
            @PathVariable Long modelConfigId) {
        return defaults.setDefault(principal.tenantId(), modelConfigId);
    }

    @PatchMapping("/{modelConfigId}/knowledge-default")
    public ModelConfig setKnowledgeDefault(
            @AuthenticationPrincipal AuthenticatedPrincipal principal,
            @PathVariable Long modelConfigId) {
        return defaults.setKnowledgeDefault(principal.tenantId(), modelConfigId);
    }

    @GetMapping("/usage/overview")
    public ModelUsagePort.UsageStatistics getUsageOverview(@AuthenticationPrincipal AuthenticatedPrincipal principal) {
        return usageService.getUsageStatistics(principal.tenantId());
    }

    @GetMapping("/usage/recent")
    public List<ModelUsageRecord> getRecentUsages(
            @AuthenticationPrincipal AuthenticatedPrincipal principal,
            @RequestParam(defaultValue = "15") int limit) {
        return usageService.listRecentUsages(principal.tenantId(), limit);
    }
}
