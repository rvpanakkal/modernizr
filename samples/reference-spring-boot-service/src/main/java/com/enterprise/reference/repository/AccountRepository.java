package com.enterprise.reference.repository;

import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.util.concurrent.ConcurrentHashMap;

@Repository
public class AccountRepository {

    private final ConcurrentHashMap<String, BigDecimal> store = new ConcurrentHashMap<>();

    public AccountRepository() {
        store.put("ACC-1001", new BigDecimal("5000.00"));
        store.put("ACC-2002", new BigDecimal("12500.00"));
    }

    public boolean exists(String accountId) {
        return store.containsKey(accountId);
    }

    public BigDecimal getBalance(String accountId) {
        return store.getOrDefault(accountId, BigDecimal.ZERO);
    }

    public void updateBalance(String accountId, BigDecimal newBalance) {
        store.put(accountId, newBalance);
    }
}
