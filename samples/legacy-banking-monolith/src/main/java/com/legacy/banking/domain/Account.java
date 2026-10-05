package com.legacy.banking.domain;

import javax.persistence.Column;
import javax.persistence.Entity;
import javax.persistence.Id;
import javax.persistence.Table;
import java.io.Serializable;
import java.math.BigDecimal;

/**
 * JPA Entity — persisted account record backed by legacy T_ACCOUNT table.
 */
@Entity
@Table(name = "T_ACCOUNT")
public class Account implements Serializable {

    private static final long serialVersionUID = 1L;

    @Id
    @Column(name = "ACCOUNT_ID", length = 20)
    private String accountId;

    @Column(name = "ACCOUNT_HOLDER", length = 100, nullable = false)
    private String accountHolder;

    @Column(name = "BALANCE", precision = 15, scale = 2, nullable = false)
    private BigDecimal balance = BigDecimal.ZERO;

    @Column(name = "STATUS", length = 20, nullable = false)
    private String status = "ACTIVE";

    @Column(name = "ACCOUNT_TYPE", length = 10)
    private String accountType;

    public Account() {}

    public Account(String accountId, String accountHolder, BigDecimal balance) {
        this.accountId = accountId;
        this.accountHolder = accountHolder;
        this.balance = balance;
    }

    public String getAccountId() { return accountId; }
    public void setAccountId(String accountId) { this.accountId = accountId; }

    public String getAccountHolder() { return accountHolder; }
    public void setAccountHolder(String accountHolder) { this.accountHolder = accountHolder; }

    public BigDecimal getBalance() { return balance; }
    public void setBalance(BigDecimal balance) { this.balance = balance; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getAccountType() { return accountType; }
    public void setAccountType(String accountType) { this.accountType = accountType; }
}
