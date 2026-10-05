package com.legacy.banking.domain;

import javax.persistence.Column;
import javax.persistence.Entity;
import javax.persistence.Id;
import javax.persistence.Table;
import java.io.Serializable;
import java.math.BigDecimal;

/**
 * JPA Entity — persisted loan application record backed by legacy T_LOAN_APPLICATION table.
 */
@Entity
@Table(name = "T_LOAN_APPLICATION")
public class LoanApplication implements Serializable {

    private static final long serialVersionUID = 1L;

    @Id
    @Column(name = "APPLICATION_ID", length = 36)
    private String applicationId;

    @Column(name = "ACCOUNT_ID", length = 20, nullable = false)
    private String accountId;

    @Column(name = "APPLICANT_NAME", length = 100, nullable = false)
    private String applicantName;

    @Column(name = "APPLICANT_EMAIL", length = 100)
    private String applicantEmail;

    @Column(name = "LOAN_TYPE", length = 20, nullable = false)
    private String loanType = "PERSONAL"; // PERSONAL, AUTO, MORTGAGE

    @Column(name = "REQUESTED_AMOUNT", precision = 15, scale = 2, nullable = false)
    private BigDecimal requestedAmount = BigDecimal.ZERO;

    @Column(name = "TERM_MONTHS", nullable = false)
    private int termMonths = 36;

    @Column(name = "INTEREST_RATE", precision = 5, scale = 2)
    private BigDecimal annualInterestRate;

    @Column(name = "MONTHLY_INCOME", precision = 15, scale = 2, nullable = false)
    private BigDecimal monthlyIncome = BigDecimal.ZERO;

    @Column(name = "CREDIT_SCORE")
    private Integer creditScore;

    @Column(name = "STATUS", length = 30, nullable = false)
    private String status = "SUBMITTED"; // SUBMITTED, APPROVED, REJECTED, DISBURSED

    @Column(name = "REJECTION_REASON", length = 255)
    private String rejectionReason;

    @Column(name = "REVIEWER_AZURE_OID", length = 50)
    private String azureAdReviewerOid;

    public LoanApplication() {}

    public LoanApplication(String applicationId, String accountId, String applicantName,
                           BigDecimal requestedAmount, int termMonths, BigDecimal monthlyIncome) {
        this.applicationId = applicationId;
        this.accountId = accountId;
        this.applicantName = applicantName;
        this.requestedAmount = requestedAmount;
        this.termMonths = termMonths;
        this.monthlyIncome = monthlyIncome;
        this.status = "SUBMITTED";
    }

    // --- Getters & Setters ---

    public String getApplicationId() { return applicationId; }
    public void setApplicationId(String applicationId) { this.applicationId = applicationId; }

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

    public BigDecimal getAnnualInterestRate() { return annualInterestRate; }
    public void setAnnualInterestRate(BigDecimal annualInterestRate) { this.annualInterestRate = annualInterestRate; }

    public BigDecimal getMonthlyIncome() { return monthlyIncome; }
    public void setMonthlyIncome(BigDecimal monthlyIncome) { this.monthlyIncome = monthlyIncome; }

    public Integer getCreditScore() { return creditScore; }
    public void setCreditScore(Integer creditScore) { this.creditScore = creditScore; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getRejectionReason() { return rejectionReason; }
    public void setRejectionReason(String rejectionReason) { this.rejectionReason = rejectionReason; }

    public String getAzureAdReviewerOid() { return azureAdReviewerOid; }
    public void setAzureAdReviewerOid(String azureAdReviewerOid) { this.azureAdReviewerOid = azureAdReviewerOid; }
}
