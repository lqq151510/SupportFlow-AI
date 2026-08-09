package com.lqq.supportflow.commerce.api;
import com.lqq.supportflow.commerce.application.QueryShipment; import com.lqq.supportflow.commerce.domain.Shipment; import com.lqq.supportflow.shared.AuthenticatedPrincipal; import org.springframework.http.HttpStatus; import org.springframework.security.core.annotation.AuthenticationPrincipal; import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/v1/customer/orders") public class CustomerShipmentController {
 private final QueryShipment service; public CustomerShipmentController(QueryShipment service){this.service=service;}
 @GetMapping("/{orderNo}/shipment") Shipment find(@AuthenticationPrincipal AuthenticatedPrincipal principal,@PathVariable String orderNo){return service.find(principal.tenantId(),principal.userId(),orderNo).orElseThrow(NotFound::new);}
 @ResponseStatus(HttpStatus.NOT_FOUND) static class NotFound extends RuntimeException { }
}
