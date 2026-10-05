package com.legacy.banking.service;

import com.legacy.banking.domain.Account;
import com.legacy.banking.gateway.CicsMainframeGateway;
import com.legacy.banking.repository.AccountRepository;
import com.legacy.banking.security.AzureAdUserPrincipal;
import javax.ejb.Stateless;
import javax.ejb.TransactionAttribute;
import javax.ejb.TransactionAttributeType;
import javax.inject.Inject;
import java.math.BigDecimal;

/**
 * Domain service EJB responsible for core fund transfer business logic.
 * Delegates persistence to AccountRepository, mainframe settlement to CicsMainframeGateway,
 * and security audits to AzureAdAuthenticationService.
 */
@Stateless
public class TransferProcessingService {

    @Inject
    private AccountRepository accountRepository;

    @Inject
    private CicsMainframeGateway cicsGateway;

    @Inject
    private AzureAdAuthenticationService authService;

    /**
     * Core business method: validates, debits, credits, and dispatches the mainframe transfer.
     *
     * @param fromAccountId source account ID
     * @param toAccountId   target account ID
     * @param amount        transfer amount (must be positive)
     * @return CICS correlation ID for audit trail
     */
    @TransactionAttribute(TransactionAttributeType.REQUIRED)
    public String processTransfer(String fromAccountId, String toAccountId, BigDecimal amount) {
        return processTransfer(fromAccountId, toAccountId, amount, null);
    }

    /**
     * Overloaded transfer method supporting authenticated Azure AD identity context.
     *
     * @param fromAccountId source account ID
     * @param toAccountId   target account ID
     * @param amount        transfer amount (must be positive)
     * @param principal     authenticated Azure AD user principal (optional)
     * @return CICS correlation ID for audit trail
     */
    @TransactionAttribute(TransactionAttributeType.REQUIRED)
    public String processTransfer(String fromAccountId, String toAccountId, BigDecimal amount, AzureAdUserPrincipal principal) {
        // Enforce RBAC if principal is provided
        if (principal != null) {
            authService.validateUserRole(principal, "ROLE_CUSTOMER");
        }

        // Business rule: amount must be positive
        if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Transfer amount must be greater than zero. Received: " + amount);
        }

        // Business rule: accounts must exist
        Account fromAccount = accountRepository.findById(fromAccountId);
        Account toAccount   = accountRepository.findById(toAccountId);

        if (fromAccount == null) {
            throw new IllegalArgumentException("Source account not found: " + fromAccountId);
        }
        if (toAccount == null) {
            throw new IllegalArgumentException("Destination account not found: " + toAccountId);
        }

        // Business rule: source account must have sufficient balance
        if (fromAccount.getBalance().compareTo(amount) < 0) {
            throw new IllegalStateException(
                "Insufficient funds in account " + fromAccountId +
                ". Balance: " + fromAccount.getBalance() + ", Required: " + amount
            );
        }

        // Business rule: accounts must be active
        if (!"ACTIVE".equals(fromAccount.getStatus())) {
            throw new IllegalStateException("Source account is not active: " + fromAccountId);
        }

        // Delegate to mainframe for atomic settlement
        String correlationId = cicsGateway.executeTransfer(fromAccountId, toAccountId, amount);

        // Update local ledger post-mainframe confirmation
        accountRepository.updateBalance(fromAccountId, fromAccount.getBalance().subtract(amount));
        accountRepository.updateBalance(toAccountId,   toAccount.getBalance().add(amount));

        if (principal != null) {
            authService.auditSecurityEvent("TRANSFER_COMPLETED", principal,
                "Transferred $" + amount + " from " + fromAccountId + " to " + toAccountId + " (CICS ref: " + correlationId + ")");
        }

        return correlationId;
    }

    public Account getAccountDetails(String accountId) {
        return accountRepository.findById(accountId);
    }
}
