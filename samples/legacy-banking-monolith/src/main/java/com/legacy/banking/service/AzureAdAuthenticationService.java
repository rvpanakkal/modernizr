package com.legacy.banking.service;

import com.legacy.banking.gateway.AzureAdGateway;
import com.legacy.banking.security.AzureAdUserPrincipal;
import javax.ejb.Stateless;
import javax.inject.Inject;

/**
 * Domain service EJB responsible for enterprise authentication, token verification,
 * Role-Based Access Control (RBAC), and security audit logging.
 * Delegates external Identity Provider verification to AzureAdGateway.
 */
@Stateless
public class AzureAdAuthenticationService {

    @Inject
    private AzureAdGateway azureAdGateway;

    /**
     * Authenticates an incoming Authorization header (Bearer token) using Azure AD.
     *
     * @param authHeader HTTP Authorization header value
     * @return validated AzureAdUserPrincipal
     * @throws SecurityException if token is missing, invalid, or expired
     */
    public AzureAdUserPrincipal authenticateBearerToken(String authHeader) {
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            throw new SecurityException("Missing or malformed Authorization header. Expected Bearer token.");
        }

        String rawToken = authHeader.substring(7).trim();
        AzureAdUserPrincipal principal = azureAdGateway.validateAzureAdJwtToken(rawToken);

        if (principal == null || principal.isExpired()) {
            throw new SecurityException("Azure AD token has expired or is invalid.");
        }

        auditSecurityEvent("AUTH_SUCCESS", principal, "Bearer token authenticated successfully");
        return principal;
    }

    /**
     * Enforces Role-Based Access Control (RBAC) on the current principal.
     *
     * @param principal authenticated user principal
     * @param requiredRole role required for the operation
     * @throws SecurityException if principal lacks required role
     */
    public void validateUserRole(AzureAdUserPrincipal principal, String requiredRole) {
        if (principal == null) {
            throw new SecurityException("Unauthenticated request: No active Azure AD security context.");
        }
        if (!principal.hasRole(requiredRole)) {
            auditSecurityEvent("ACCESS_DENIED", principal, "Required role missing: " + requiredRole);
            throw new SecurityException(
                "Access denied for user " + principal.getPreferredUsername() +
                ". Missing required role: " + requiredRole
            );
        }
    }

    /**
     * Development and testing helper to generate a valid mock principal for a given role.
     */
    public AzureAdUserPrincipal generateMockSession(String userRole) {
        String mockToken = "mock-" + (userRole != null ? userRole.toLowerCase() : "customer") + "-token";
        return azureAdGateway.validateAzureAdJwtToken(mockToken);
    }

    /**
     * Records an immutable security audit event for SOC2 and PCI-DSS compliance.
     */
    public void auditSecurityEvent(String eventType, AzureAdUserPrincipal principal, String detail) {
        String username = (principal != null) ? principal.getPreferredUsername() : "ANONYMOUS";
        String oid = (principal != null) ? principal.getOid() : "N/A";
        System.out.printf("[SECURITY AUDIT] event=%s | user=%s | oid=%s | detail=%s%n",
                eventType, username, oid, detail);
    }
}
