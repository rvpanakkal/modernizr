package com.legacy.banking.gateway;

import com.legacy.banking.security.AzureAdUserPrincipal;
import javax.ejb.Stateless;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

/**
 * Integration boundary — EJB gateway connecting to Microsoft Azure Active Directory (Entra ID)
 * via OpenID Connect (OIDC) and OAuth 2.0 REST endpoints.
 * Simulates Microsoft Identity Platform v2.0 token validation and JWKS key verification.
 */
@Stateless
public class AzureAdGateway {

    private static final String AZURE_AD_BASE_URL    = "https://login.microsoftonline.com";
    private static final String EXPECTED_TENANT_ID   = "72f988bf-86f1-41af-91ab-2d7cd011db47";
    private static final String CLIENT_ID            = "banking-monolith-app-id";
    private static final int    TIMEOUT_MS           = 3_000;

    /**
     * Validates an incoming Azure AD Bearer JWT token against Microsoft Identity Platform.
     * Simulates signature validation via JWKS, tenant ID verification, and claims extraction.
     *
     * @param jwtToken Bearer token string
     * @return AzureAdUserPrincipal populated from validated token claims
     */
    public AzureAdUserPrincipal validateAzureAdJwtToken(String jwtToken) {
        if (jwtToken == null || jwtToken.trim().isEmpty()) {
            throw new SecurityException("Missing or empty Azure AD Bearer token.");
        }

        // Simulate network call to Microsoft JWKS endpoint
        System.out.printf("[Azure AD Gateway] Verifying token against %s/%s/discovery/v2.0/keys (timeout=%dms)%n",
                AZURE_AD_BASE_URL, EXPECTED_TENANT_ID, TIMEOUT_MS);

        // Strip prefix if present
        String token = jwtToken.startsWith("Bearer ") ? jwtToken.substring(7).trim() : jwtToken.trim();

        // Check for simulated mock tokens or extract claims
        AzureAdUserPrincipal principal = new AzureAdUserPrincipal();
        principal.setAccessToken(token);
        principal.setTenantId(EXPECTED_TENANT_ID);

        long now = System.currentTimeMillis();
        principal.setIssuedAtTimestamp(now);
        principal.setExpiresAtTimestamp(now + 3600_000L); // 1 hour validity

        if (token.contains("teller") || token.contains("TELLER")) {
            principal.setOid("oid-teller-" + UUID.randomUUID().toString().substring(0, 8));
            principal.setPreferredUsername("alex.teller@enterprise-bank.com");
            principal.setDisplayName("Alex Teller");
            principal.addRole("ROLE_TELLER");
            principal.addRole("ROLE_CUSTOMER");
            principal.addRole("Banking.Transfer");
        } else if (token.contains("officer") || token.contains("OFFICER")) {
            principal.setOid("oid-officer-" + UUID.randomUUID().toString().substring(0, 8));
            principal.setPreferredUsername("sarah.officer@enterprise-bank.com");
            principal.setDisplayName("Sarah Officer");
            principal.addRole("ROLE_LOAN_OFFICER");
            principal.addRole("ROLE_TELLER");
            principal.addRole("Banking.Loan.Apply");
            principal.addRole("Banking.Loan.Approve");
        } else if (token.contains("admin") || token.contains("ADMIN")) {
            principal.setOid("oid-admin-" + UUID.randomUUID().toString().substring(0, 8));
            principal.setPreferredUsername("admin.user@enterprise-bank.com");
            principal.setDisplayName("System Administrator");
            principal.addRole("ROLE_ADMIN");
            principal.addRole("Banking.Admin");
            principal.addRole("Banking.Transfer");
            principal.addRole("Banking.Loan.Approve");
        } else {
            // Default customer identity
            principal.setOid("oid-cust-" + UUID.randomUUID().toString().substring(0, 8));
            principal.setPreferredUsername("customer.user@enterprise-bank.com");
            principal.setDisplayName("Customer User");
            principal.addRole("ROLE_CUSTOMER");
            principal.addRole("Banking.Transfer");
            principal.addRole("Banking.Loan.Apply");
        }

        System.out.printf("[Azure AD Gateway] Token successfully validated for user: %s (oid=%s, roles=%s)%n",
                principal.getPreferredUsername(), principal.getOid(), principal.getRoles());

        return principal;
    }

    /**
     * Simulates OAuth 2.0 authorization code exchange for Azure AD ID/Access tokens.
     */
    public String exchangeAuthorizationCode(String authCode) {
        System.out.printf("[Azure AD Gateway] Exchanging auth code for token at %s/%s/oauth2/v2.0/token%n",
                AZURE_AD_BASE_URL, EXPECTED_TENANT_ID);
        return "mock-azure-ad-jwt-token-for-" + authCode;
    }

    /**
     * Simulates Microsoft Graph API call /v1.0/users/{oid} to fetch extended profile information.
     */
    public String fetchUserProfile(String userOid) {
        System.out.printf("[Azure AD Gateway] Fetching user profile from Graph API for oid=%s%n", userOid);
        return String.format("{\"id\":\"%s\",\"company\":\"Enterprise Bank\",\"jobTitle\":\"Banking Analyst\"}", userOid);
    }
}
