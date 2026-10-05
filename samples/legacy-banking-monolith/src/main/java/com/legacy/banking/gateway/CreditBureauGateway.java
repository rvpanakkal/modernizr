package com.legacy.banking.gateway;

import javax.ejb.Stateless;
import java.math.BigDecimal;
import java.util.UUID;

/**
 * Integration boundary — EJB gateway to external Credit Bureaus (Equifax / Experian / TransUnion).
 * Simulates synchronous credit report queries and automated risk scoring via mainframe protocol.
 */
@Stateless
public class CreditBureauGateway {

    private static final String BUREAU_ENDPOINT = "tcp://creditbureau.enterprise.local:5500";
    private static final String PROGRAM_ID      = "CRD002";
    private static final int    TIMEOUT_MS      = 4_000;

    /**
     * Inquires credit bureau mainframe for borrower credit score (FICO rating 300 - 850).
     *
     * @param applicantName applicant full name
     * @param accountId applicant bank account ID
     * @param monthlyIncome verified monthly income
     * @return FICO score integer (300 - 850)
     */
    public int requestCreditScore(String applicantName, String accountId, BigDecimal monthlyIncome) {
        String inquiryId = UUID.randomUUID().toString();
        String request = String.format("%s|%s|%s|%s|%s",
                PROGRAM_ID, inquiryId, applicantName, accountId, monthlyIncome.toPlainString());

        System.out.printf("[Credit Bureau Gateway] → %s (timeout=%dms): %s%n",
                BUREAU_ENDPOINT, TIMEOUT_MS, request);

        // Deterministic simulation based on account ID or name
        if (accountId.endsWith("9") || applicantName.toLowerCase().contains("bad")) {
            return 540; // Subprime / High risk
        } else if (accountId.endsWith("1") || applicantName.toLowerCase().contains("prime")) {
            return 780; // Super-prime
        } else {
            return 710; // Prime
        }
    }

    /**
     * Inquires credit bureau for total monthly external debt obligations.
     *
     * @param accountId applicant account identifier
     * @return monthly debt obligation amount
     */
    public BigDecimal queryExistingDebtObligations(String accountId) {
        System.out.printf("[Credit Bureau Gateway] Querying debt registry for accountId=%s%n", accountId);
        // Simulate existing monthly debt payments
        if (accountId.endsWith("8")) {
            return new BigDecimal("2500.00");
        }
        return new BigDecimal("450.00");
    }
}
