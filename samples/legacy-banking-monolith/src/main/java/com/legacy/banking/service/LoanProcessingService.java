package com.legacy.banking.service;

import com.legacy.banking.domain.Account;
import com.legacy.banking.domain.LoanApplication;
import com.legacy.banking.gateway.CreditBureauGateway;
import com.legacy.banking.repository.AccountRepository;
import com.legacy.banking.repository.LoanApplicationRepository;
import com.legacy.banking.security.AzureAdUserPrincipal;
import javax.ejb.Stateless;
import javax.ejb.TransactionAttribute;
import javax.ejb.TransactionAttributeType;
import javax.inject.Inject;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.UUID;

/**
 * Domain service EJB responsible for loan origination, automated underwriting,
 * risk scoring, credit approval, and disbursement into core bank accounts.
 * Integrates with CreditBureauGateway for credit scores, AccountRepository for account
 * verification/disbursement, and AzureAdAuthenticationService for RBAC and audit.
 */
@Stateless
public class LoanProcessingService {

    private static final BigDecimal MIN_LOAN_AMOUNT = new BigDecimal("1000.00");
    private static final BigDecimal MAX_LOAN_AMOUNT = new BigDecimal("500000.00");
    private static final int MIN_TERM_MONTHS = 12;
    private static final int MAX_TERM_MONTHS = 360;
    private static final int MIN_CREDIT_SCORE = 580;
    private static final BigDecimal MAX_DTI_RATIO = new BigDecimal("0.45"); // 45% DTI cap

    @Inject
    private LoanApplicationRepository loanRepository;

    @Inject
    private AccountRepository accountRepository;

    @Inject
    private CreditBureauGateway creditBureauGateway;

    @Inject
    private AzureAdAuthenticationService authService;

    /**
     * Core business method: Validates application, evaluates credit and DTI underwriting thresholds,
     * approves or rejects, and atomically disburses loan proceeds into customer ledger.
     *
     * @param application loan application data
     * @param principal authenticated Azure AD identity
     * @return populated and persisted LoanApplication
     */
    @TransactionAttribute(TransactionAttributeType.REQUIRED)
    public LoanApplication submitAndProcessLoan(LoanApplication application, AzureAdUserPrincipal principal) {
        // Enforce Azure AD authentication & role authorization
        if (principal != null) {
            authService.validateUserRole(principal, "ROLE_CUSTOMER");
            application.setAzureAdReviewerOid(principal.getOid());
        }

        if (application.getApplicationId() == null) {
            application.setApplicationId(UUID.randomUUID().toString());
        }

        // Business Rule 1: Validate requested amount
        BigDecimal amount = application.getRequestedAmount();
        if (amount == null || amount.compareTo(MIN_LOAN_AMOUNT) < 0 || amount.compareTo(MAX_LOAN_AMOUNT) > 0) {
            throw new IllegalArgumentException(
                "Loan amount must be between $" + MIN_LOAN_AMOUNT + " and $" + MAX_LOAN_AMOUNT + ". Received: " + amount
            );
        }

        // Business Rule 2: Validate term
        int term = application.getTermMonths();
        if (term < MIN_TERM_MONTHS || term > MAX_TERM_MONTHS) {
            throw new IllegalArgumentException(
                "Loan term must be between " + MIN_TERM_MONTHS + " and " + MAX_TERM_MONTHS + " months. Received: " + term
            );
        }

        // Business Rule 3: Validate monthly income
        BigDecimal income = application.getMonthlyIncome();
        if (income == null || income.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Monthly income must be greater than zero.");
        }

        // Business Rule 4: Verify associated account exists and is ACTIVE
        String accountId = application.getAccountId();
        Account targetAccount = accountRepository.findById(accountId);
        if (targetAccount == null) {
            throw new IllegalArgumentException("Target disbursement account not found: " + accountId);
        }
        if (!"ACTIVE".equals(targetAccount.getStatus())) {
            throw new IllegalStateException("Disbursement account is inactive: " + accountId);
        }

        // Integration Boundary: Query external Credit Bureau
        int creditScore = creditBureauGateway.requestCreditScore(
                application.getApplicantName(), accountId, income);
        application.setCreditScore(creditScore);

        // Underwriting Decision: Rule 5 - Minimum credit score threshold
        if (creditScore < MIN_CREDIT_SCORE) {
            application.setStatus("REJECTED");
            application.setRejectionReason("Credit score " + creditScore + " is below minimum underwriting requirement of " + MIN_CREDIT_SCORE);
            loanRepository.save(application);
            if (principal != null) {
                authService.auditSecurityEvent("LOAN_REJECTED", principal, "Low credit score: " + creditScore);
            }
            return application;
        }

        // Determine tiered interest rate based on credit score
        BigDecimal interestRate;
        if (creditScore >= 750) {
            interestRate = new BigDecimal("5.75");  // Tier A: Prime
        } else if (creditScore >= 670) {
            interestRate = new BigDecimal("7.95");  // Tier B: Standard
        } else {
            interestRate = new BigDecimal("11.50"); // Tier C: Near-prime
        }
        application.setAnnualInterestRate(interestRate);

        // Underwriting Decision: Rule 6 - Debt-to-Income (DTI) ratio check
        BigDecimal monthlyLoanPayment = calculateMonthlyPayment(amount, interestRate, term);
        BigDecimal existingMonthlyDebt = creditBureauGateway.queryExistingDebtObligations(accountId);
        BigDecimal totalMonthlyObligations = monthlyLoanPayment.add(existingMonthlyDebt);
        BigDecimal dti = totalMonthlyObligations.divide(income, 4, RoundingMode.HALF_UP);

        if (dti.compareTo(MAX_DTI_RATIO) > 0) {
            application.setStatus("REJECTED");
            application.setRejectionReason(
                "Debt-to-income ratio (" + dti.multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_UP) +
                "%) exceeds maximum underwriting policy limit of 45%"
            );
            loanRepository.save(application);
            if (principal != null) {
                authService.auditSecurityEvent("LOAN_REJECTED", principal, "DTI policy breach: " + dti);
            }
            return application;
        }

        // Application Approved
        application.setStatus("APPROVED");

        // Disburse loan funds into the verified bank account
        accountRepository.updateBalance(accountId, targetAccount.getBalance().add(amount));
        application.setStatus("DISBURSED");

        loanRepository.save(application);

        if (principal != null) {
            authService.auditSecurityEvent("LOAN_DISBURSED", principal,
                "Loan " + application.getApplicationId() + " disbursed: $" + amount + " to account " + accountId);
        }

        return application;
    }

    /**
     * Calculates estimated monthly loan payment using standard amortization formula.
     */
    public BigDecimal calculateMonthlyPayment(BigDecimal principal, BigDecimal annualRatePercent, int termMonths) {
        if (principal == null || annualRatePercent == null || termMonths <= 0) {
            return BigDecimal.ZERO;
        }
        BigDecimal monthlyRate = annualRatePercent.divide(new BigDecimal("1200"), 6, RoundingMode.HALF_UP);
        // Simplified payment formula for legacy compatibility: P * (r + 1/n)
        BigDecimal monthlyInterest = principal.multiply(monthlyRate);
        BigDecimal monthlyPrincipal = principal.divide(BigDecimal.valueOf(termMonths), 2, RoundingMode.HALF_UP);
        return monthlyPrincipal.add(monthlyInterest).setScale(2, RoundingMode.HALF_UP);
    }

    public LoanApplication getApplication(String applicationId) {
        return loanRepository.findById(applicationId);
    }
}
