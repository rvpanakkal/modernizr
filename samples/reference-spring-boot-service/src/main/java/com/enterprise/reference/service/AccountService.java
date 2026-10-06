package com.enterprise.reference.service;

import com.enterprise.reference.controller.SampleAccountController.AccountResponse;
import com.enterprise.reference.repository.AccountRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.NoSuchElementException;

@Service
@Transactional
public class AccountService {

    private final AccountRepository accountRepository;

    public AccountService(AccountRepository accountRepository) {
        this.accountRepository = accountRepository;
    }

    @Transactional(readOnly = true)
    public AccountResponse getAccount(String accountId) {
        if (!accountRepository.exists(accountId)) {
            throw new NoSuchElementException("Account not found: " + accountId);
        }
        BigDecimal balance = accountRepository.getBalance(accountId);
        return new AccountResponse(accountId, "Enterprise Customer", balance, "ACTIVE", Instant.now());
    }

    public AccountResponse adjustBalance(String accountId, BigDecimal amount, String reason) {
        if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Adjustment amount must be positive");
        }
        if (!accountRepository.exists(accountId)) {
            throw new NoSuchElementException("Account not found: " + accountId);
        }
        BigDecimal current = accountRepository.getBalance(accountId);
        BigDecimal newBalance = current.add(amount);
        accountRepository.updateBalance(accountId, newBalance);
        return new AccountResponse(accountId, "Enterprise Customer", newBalance, "ACTIVE", Instant.now());
    }
}
