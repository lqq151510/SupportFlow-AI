package com.lqq.supportflow.model.api;
import com.lqq.supportflow.model.application.CreateModelConfigService;
import com.lqq.supportflow.model.application.ListModelConfigsService;
import com.lqq.supportflow.model.application.ProbeModelConnectionService;
import com.lqq.supportflow.model.domain.ModelConfig;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import jakarta.validation.Valid;
import java.net.URI;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
@RestController @RequestMapping("/api/v1/admin/models") public class AdminModelConfigController {
    private final CreateModelConfigService service; private final ProbeModelConnectionService probe; private final ListModelConfigsService list;
    public AdminModelConfigController(CreateModelConfigService service, ProbeModelConnectionService probe, ListModelConfigsService list) { this.service=service;this.probe=probe;this.list=list; }
    @GetMapping java.util.List<ModelConfig> list(@AuthenticationPrincipal AuthenticatedPrincipal principal) { return list.list(principal.tenantId()); }
    @PostMapping ResponseEntity<ModelConfig> create(@AuthenticationPrincipal AuthenticatedPrincipal principal,@Valid @RequestBody CreateModelConfigRequest request) {
        ModelConfig result=service.create(principal.tenantId(),request.name(),request.protocol(),request.baseUrl(),request.modelName(),request.apiKey(),request.isDefault());
        return ResponseEntity.created(URI.create("/api/v1/admin/models/"+result.id())).body(result);
    }
    @PostMapping("/probe") ProbeModelConnectionService.ProbeResult probe(@Valid @RequestBody ModelProbeRequest request){return probe.probe(request.baseUrl(),request.apiKey());}
}
