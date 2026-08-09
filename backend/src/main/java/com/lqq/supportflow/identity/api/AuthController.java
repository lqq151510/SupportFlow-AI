package com.lqq.supportflow.identity.api;
import com.lqq.supportflow.identity.application.LoginService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import com.lqq.supportflow.identity.domain.AccessTokenSubject;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final LoginService service;

    public AuthController(LoginService service) {
        this.service = service;
    }

    @PostMapping("/login")
    LoginService.TokenPair login(@Valid @RequestBody LoginRequest request) {
        return service.login(request.tenantCode(), request.email(), request.password());
    }

    @PostMapping("/refresh")
    LoginService.TokenPair refresh(@Valid @RequestBody RefreshTokenRequest request) {
        return service.refresh(request.refreshToken());
    }

    @PostMapping("/logout")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    void logout(@Valid @RequestBody RefreshTokenRequest request) {
        service.logout(request.refreshToken());
    }

    @org.springframework.web.bind.annotation.GetMapping("/session")
    AccessTokenSubject session(@AuthenticationPrincipal AccessTokenSubject subject) {
        return subject;
    }
}
