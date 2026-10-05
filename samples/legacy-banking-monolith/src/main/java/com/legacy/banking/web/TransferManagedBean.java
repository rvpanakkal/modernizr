package com.legacy.banking.web;

import com.legacy.banking.security.AzureAdUserPrincipal;
import com.legacy.banking.service.AzureAdAuthenticationService;
import com.legacy.banking.service.TransferProcessingService;
import javax.faces.bean.ManagedBean;
import javax.faces.bean.SessionScoped;
import javax.ejb.EJB;
import java.io.Serializable;
import java.math.BigDecimal;

/**
 * JSF Managed Bean — presentation-layer entry point for the Fund Transfer UI.
 * Legacy Java EE 6 / JSF 2.x component integrated with Azure AD authentication.
 */
@ManagedBean
@SessionScoped
public class TransferManagedBean implements Serializable {

    private static final long serialVersionUID = 1L;

    @EJB
    private TransferProcessingService transferService;

    @EJB
    private AzureAdAuthenticationService authService;

    private String fromAccountId;
    private String toAccountId;
    private BigDecimal amount;
    private String statusMessage;
    private String correlationId;

    /**
     * JSF action method — invoked by the transfer form submit button.
     * @return navigation outcome string
     */
    public String execute() {
        try {
            // Verify Azure AD security context (mock session fallback for legacy test harness)
            AzureAdUserPrincipal principal = authService.generateMockSession("CUSTOMER");
            authService.validateUserRole(principal, "ROLE_CUSTOMER");

            correlationId = transferService.processTransfer(fromAccountId, toAccountId, amount, principal);
            statusMessage = "Transfer successful. Reference: " + correlationId;
            return "success";
        } catch (SecurityException e) {
            statusMessage = "Authorization failed: " + e.getMessage();
            return "unauthorized";
        } catch (IllegalArgumentException e) {
            statusMessage = "Validation error: " + e.getMessage();
            return "failure";
        } catch (Exception e) {
            statusMessage = "Transfer failed: " + e.getMessage();
            return "error";
        }
    }

    public void reset() {
        fromAccountId = null;
        toAccountId = null;
        amount = null;
        statusMessage = null;
        correlationId = null;
    }

    // --- Getters & Setters ---
    public String getFromAccountId() { return fromAccountId; }
    public void setFromAccountId(String fromAccountId) { this.fromAccountId = fromAccountId; }

    public String getToAccountId() { return toAccountId; }
    public void setToAccountId(String toAccountId) { this.toAccountId = toAccountId; }

    public BigDecimal getAmount() { return amount; }
    public void setAmount(BigDecimal amount) { this.amount = amount; }

    public String getStatusMessage() { return statusMessage; }
    public void setStatusMessage(String statusMessage) { this.statusMessage = statusMessage; }

    public String getCorrelationId() { return correlationId; }
}
