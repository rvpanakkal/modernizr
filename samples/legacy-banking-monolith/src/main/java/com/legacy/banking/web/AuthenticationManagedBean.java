package com.legacy.banking.web;

import com.legacy.banking.security.AzureAdUserPrincipal;
import com.legacy.banking.service.AzureAdAuthenticationService;
import javax.ejb.EJB;
import javax.faces.bean.ManagedBean;
import javax.faces.bean.SessionScoped;
import java.io.Serializable;

/**
 * JSF Managed Bean — Presentation layer entry point for Azure AD authentication and user session management.
 * Manages SSO login redirects, token validation, user context, and UI role authorization flags.
 */
@ManagedBean(name = "authBean")
@SessionScoped
public class AuthenticationManagedBean implements Serializable {

    private static final long serialVersionUID = 1L;

    @EJB
    private AzureAdAuthenticationService authService;

    private AzureAdUserPrincipal currentUser;
    private String rawBearerToken;
    private String selectedRole = "CUSTOMER";
    private String authStatusMessage;
    private boolean authenticated = false;

    /**
     * JSF Action: Authenticates via Azure AD Bearer token received from SSO callback.
     * @return navigation outcome
     */
    public String loginWithAzureAd() {
        try {
            if (rawBearerToken == null || rawBearerToken.trim().isEmpty()) {
                authStatusMessage = "Azure AD token is required.";
                return "failure";
            }

            String headerValue = rawBearerToken.startsWith("Bearer ") ? rawBearerToken : "Bearer " + rawBearerToken;
            currentUser = authService.authenticateBearerToken(headerValue);
            authenticated = true;
            authStatusMessage = "Welcome, " + currentUser.getDisplayName() + " (" + currentUser.getPreferredUsername() + ")";
            return "dashboard";
        } catch (SecurityException e) {
            authenticated = false;
            currentUser = null;
            authStatusMessage = "Authentication failed: " + e.getMessage();
            return "login_error";
        }
    }

    /**
     * JSF Action: Fast-path login for legacy monolith testing using a mock Azure AD role.
     * @return navigation outcome
     */
    public String loginAsMockRole() {
        try {
            currentUser = authService.generateMockSession(selectedRole);
            authenticated = true;
            authStatusMessage = "Authenticated as mock user: " + currentUser.getDisplayName() + " [" + selectedRole + "]";
            return "dashboard";
        } catch (Exception e) {
            authStatusMessage = "Mock login failed: " + e.getMessage();
            return "login_error";
        }
    }

    /**
     * JSF Action: Logs out the current user and invalidates session identity context.
     * @return navigation outcome
     */
    public String logout() {
        if (currentUser != null) {
            authService.auditSecurityEvent("LOGOUT", currentUser, "User signed out from JSF session");
        }
        currentUser = null;
        authenticated = false;
        rawBearerToken = null;
        authStatusMessage = "You have been logged out.";
        return "login";
    }

    /**
     * Evaluates whether the current authenticated user has the specified enterprise role.
     */
    public boolean hasRole(String role) {
        if (!authenticated || currentUser == null) {
            return false;
        }
        return currentUser.hasRole(role);
    }

    // --- Getters & Setters ---

    public AzureAdUserPrincipal getCurrentUser() { return currentUser; }

    public String getRawBearerToken() { return rawBearerToken; }
    public void setRawBearerToken(String rawBearerToken) { this.rawBearerToken = rawBearerToken; }

    public String getSelectedRole() { return selectedRole; }
    public void setSelectedRole(String selectedRole) { this.selectedRole = selectedRole; }

    public String getAuthStatusMessage() { return authStatusMessage; }
    public void setAuthStatusMessage(String authStatusMessage) { this.authStatusMessage = authStatusMessage; }

    public boolean isAuthenticated() { return authenticated; }
}
