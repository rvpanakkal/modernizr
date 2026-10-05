package com.legacy.banking.repository;

import com.legacy.banking.domain.Account;
import javax.ejb.Stateless;
import javax.persistence.EntityManager;
import javax.persistence.PersistenceContext;
import javax.persistence.TypedQuery;
import java.math.BigDecimal;
import java.util.List;

/**
 * Data access EJB for Account entities.
 * Wraps JPA EntityManager operations.
 */
@Stateless
public class AccountRepository {

    @PersistenceContext(unitName = "bankingPU")
    private EntityManager em;

    public Account findById(String accountId) {
        return em.find(Account.class, accountId);
    }

    public List<Account> findByHolder(String holderName) {
        TypedQuery<Account> query = em.createQuery(
            "SELECT a FROM Account a WHERE a.accountHolder = :holder", Account.class);
        query.setParameter("holder", holderName);
        return query.getResultList();
    }

    public void updateBalance(String accountId, BigDecimal newBalance) {
        Account account = em.find(Account.class, accountId);
        if (account != null) {
            account.setBalance(newBalance);
            em.merge(account);
        }
    }

    public void save(Account account) {
        em.persist(account);
    }

    public void delete(String accountId) {
        Account account = em.find(Account.class, accountId);
        if (account != null) {
            em.remove(account);
        }
    }
}
