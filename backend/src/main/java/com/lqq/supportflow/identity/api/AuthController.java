package com.lqq.supportflow.identity.api;
import com.lqq.supportflow.identity.application.LoginService;
import com.lqq.supportflow.identity.application.ChangePasswordService;
import com.lqq.supportflow.identity.application.CurrentUserProfileService;
import com.lqq.supportflow.identity.domain.CurrentUserProfile;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final LoginService service;
    private final ChangePasswordService changePassword;
    private final CurrentUserProfileService profiles;

    public AuthController(LoginService service, ChangePasswordService changePassword, CurrentUserProfileService profiles) {
        this.service = service;
        this.changePassword = changePassword;
        this.profiles = profiles;
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

    @GetMapping("/session")
    AuthenticatedPrincipal session(@AuthenticationPrincipal AuthenticatedPrincipal subject) {
        return subject;
    }

    @GetMapping("/profile")
    CurrentUserProfile profile(@AuthenticationPrincipal AuthenticatedPrincipal principal) {
        return profiles.get(principal);
    }

    @PatchMapping("/profile")
    CurrentUserProfile updateProfile(
            @AuthenticationPrincipal AuthenticatedPrincipal principal,
            @Valid @RequestBody UpdateCurrentUserProfileRequest request) {
        return profiles.updateDisplayName(principal, request.displayName());
    }

    @PostMapping("/change-password")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    void changePassword(
            @AuthenticationPrincipal AuthenticatedPrincipal principal,
            @Valid @RequestBody ChangePasswordRequest request) {
        changePassword.change(principal.userId(), principal.tenantId(), request.currentPassword(), request.newPassword());
    }
}
