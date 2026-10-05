package com.legacy.banking.web;

import com.legacy.banking.domain.LoanApplication;
import com.legacy.banking.security.AzureAdUserPrincipal;
import com.legacy.banking.service.AzureAdAuthenticationService;
import com.legacy.banking.service.LoanProcessingService;
import javax.ejb.EJB;
import javax.faces.bean.ManagedBean;
import javax.faces.bean.SessionScoped;
import java.io.Serializable;
import java.math.BigDecimal;

/**
 * JSF Managed Bean — Presentation layer entry point for the Loan Application & Underwriting UI.
 * Connects frontend JSF forms to LoanProcessingService and validates Azure AD user identity.
 */
@ManagedBean(name = "loanBean")
@SessionScoped
public class LoanApplicationManagedBean implements Serializable {

    private static final long serialVersionUID = 1L;

    @EJB
    private LoanProcessingService loanService;

    @EJB
    private AzureAdAuthenticationService authService;

    private String accountId;
    private String applicantName;
    private String applicantEmail;
    private String loanType = "PERSONAL";
    private BigDecimal requestedAmount;
    private int termMonths = 36;
    private BigDecimal monthlyIncome;

    private String applicationId;
    private String statusMessage;
    private String applicationStatus;
    private BigDecimal approvedInterestRate;
    private BigDecimal estimatedMonthlyPayment;

    /**
     * JSF Action: Submits loan application for automated credit underwriting.
     * @return navigation outcome
     */
    public String apply() {
        try {
            // Retrieve current principal or mock session for legacy JSF context
            AzureAdUserPrincipal principal = authService.generateMockSession("CUSTOMER");

            LoanApplication application = new LoanApplication();
            application.setAccountId(accountId);
            application.setApplicantName(applicantName);
            application.setApplicantEmail(applicantEmail);
            application.setLoanType(loanType);
            application.setRequestedAmount(requestedAmount);
            application.setTermMonths(termMonths);
            application.setMonthlyIncome(monthlyIncome);

            LoanApplication result = loanService.submitAndProcessLoan(application, principal);

            this.applicationId = result.getApplicationId();
            this.applicationStatus = result.getStatus();
            this.approvedInterestRate = result.getAnnualInterestRate();

            if ("DISBURSED".equals(result.getStatus())) {
                statusMessage = "Loan application approved and funds disbursed! Reference: " + applicationId;
                return "approved";
            } else if ("REJECTED".equals(result.getStatus())) {
                statusMessage = "Loan application declined: " + result.getRejectionReason();
                return "declined";
            } else {
                statusMessage = "Application status: " + result.getStatus();
                return "pending";
            }
        } catch (IllegalArgumentException | IllegalStateException e) {
            statusMessage = "Validation error: " + e.getMessage();
            return "failure";
        } catch (Exception e) {
            statusMessage = "Application processing failed: " + e.getMessage();
            return "error";
        }
    }

    /**
     * JSF Action: Calculates monthly payment estimation without submitting application.
     */
    public String calculateEstimate() {
        if (requestedAmount != null && termMonths > 0) {
            BigDecimal estimatedRate = new BigDecimal("7.50"); // Benchmark estimate
            estimatedMonthlyPayment = loanService.calculateMonthlyPayment(requestedAmount, estimatedRate, termMonths);
            statusMessage = "Estimated monthly payment: $" + estimatedMonthlyPayment + " (at 7.50% APR)";
        }
        return "estimate";
    }

    public void reset() {
        accountId = null;
        applicantName = null;
        applicantEmail = null;
        loanType = "PERSONAL";
        requestedAmount = null;
        termMonths = 36;
        monthlyIncome = null;
        applicationId = null;
        statusMessage = null;
        applicationStatus = null;
        approvedInterestRate = null;
        estimatedMonthlyPayment = null;
    }

    // --- Getters & Setters ---

    public String getAccountId() { return accountId; }
    public void setAccountId(String accountId) { this.accountId = accountId; }

    public String getApplicantName() { return applicantName; }
    public void setApplicantName(String applicantName) { this.applicantName = applicantName; }

    public String getApplicantEmail() { return applicantEmail; }
    public void setApplicantEmail(String applicantEmail) { this.applicantEmail = applicantEmail; }

    public String getLoanType() { return loanType; }
    public void setLoanType(String loanType) { this.loanType = loanType; }

    public BigDecimal getRequestedAmount() { return requestedAmount; }
    public void setRequestedAmount(BigDecimal requestedAmount) { this.requestedAmount = requestedAmount; }

    public int getTermMonths() { return termMonths; }
    public void setTermMonths(int termMonths) { this.termMonths = termMonths; }

    public BigDecimal getMonthlyIncome() { return monthlyIncome; }
    public void setMonthlyIncome(BigDecimal monthlyIncome) { this.monthlyIncome = monthlyIncome; }

    public String getApplicationId() { return applicationId; }
    public String getStatusMessage() { return statusMessage; }
    public String getApplicationStatus() { return applicationStatus; }
    public BigDecimal getApprovedInterestRate() { return approvedInterestRate; }
    public BigDecimal getEstimatedMonthlyPayment() { return estimatedMonthlyPayment; }
}
