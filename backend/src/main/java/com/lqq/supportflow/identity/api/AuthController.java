package com.lqq.supportflow.identity.api;
import com.lqq.supportflow.identity.application.LoginService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/v1/auth")
public class AuthController { private final LoginService service; public AuthController(LoginService service){this.service=service;}
 @PostMapping("/login") LoginService.TokenPair login(@Valid @RequestBody LoginRequest r){return service.login(r.tenantCode(),r.email(),r.password());}}
