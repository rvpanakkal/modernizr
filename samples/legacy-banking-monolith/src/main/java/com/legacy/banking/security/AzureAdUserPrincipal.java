package com.legacy.banking.security;

import java.io.Serializable;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

/**
 * Security Principal representing an authenticated Azure Active Directory (Entra ID) identity.
 * Contains standard claims extracted from Microsoft identity platform v2.0 JWT tokens:
 * oid (Object ID), upn (User Principal Name), tid (Tenant ID), roles, and display name.
 */
public class AzureAdUserPrincipal implements Serializable {

    private static final long serialVersionUID = 1L;

    private String oid;                 // Azure AD Object Identifier GUID
    private String preferredUsername;   // UPN / Corporate Email
    private String displayName;         // User Full Name
    private String tenantId;            // Azure AD Directory Tenant ID
    private String accessToken;         // Bearer token (raw JWT string)
    private Set<String> roles = new HashSet<>();
    private long issuedAtTimestamp;
    private long expiresAtTimestamp;

    public AzureAdUserPrincipal() {}

    public AzureAdUserPrincipal(String oid, String preferredUsername, String displayName,
                                String tenantId, Set<String> roles) {
        this.oid = oid;
        this.preferredUsername = preferredUsername;
        this.displayName = displayName;
        this.tenantId = tenantId;
        if (roles != null) {
            this.roles.addAll(roles);
        }
    }

    public boolean hasRole(String role) {
        if (role == null || roles == null) {
            return false;
        }
        return roles.contains(role) || roles.contains("ROLE_" + role);
    }

    public boolean isExpired() {
        if (expiresAtTimestamp <= 0) {
            return false;
        }
        return System.currentTimeMillis() > expiresAtTimestamp;
    }

    // --- Getters & Setters ---

    public String getOid() { return oid; }
    public void setOid(String oid) { this.oid = oid; }

    public String getPreferredUsername() { return preferredUsername; }
    public void setPreferredUsername(String preferredUsername) { this.preferredUsername = preferredUsername; }

    public String getDisplayName() { return displayName; }
    public void setDisplayName(String displayName) { this.displayName = displayName; }

    public String getTenantId() { return tenantId; }
    public void setTenantId(String tenantId) { this.tenantId = tenantId; }

    public String getAccessToken() { return accessToken; }
    public void setAccessToken(String accessToken) { this.accessToken = accessToken; }

    public Set<String> getRoles() { return Collections.unmodifiableSet(roles); }
    public void setRoles(Set<String> roles) {
        this.roles = roles != null ? new HashSet<>(roles) : new HashSet<>();
    }

    public void addRole(String role) {
        if (this.roles == null) {
            this.roles = new HashSet<>();
        }
        this.roles.add(role);
    }

    public long getIssuedAtTimestamp() { return issuedAtTimestamp; }
    public void setIssuedAtTimestamp(long issuedAtTimestamp) { this.issuedAtTimestamp = issuedAtTimestamp; }

    public long getExpiresAtTimestamp() { return expiresAtTimestamp; }
    public void setExpiresAtTimestamp(long expiresAtTimestamp) { this.expiresAtTimestamp = expiresAtTimestamp; }

    @Override
    public String toString() {
        return "AzureAdUserPrincipal{" +
                "oid='" + oid + '\'' +
                ", preferredUsername='" + preferredUsername + '\'' +
                ", tenantId='" + tenantId + '\'' +
                ", roles=" + roles +
                '}';
    }
}
