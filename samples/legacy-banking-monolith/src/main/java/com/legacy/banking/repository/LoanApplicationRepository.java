package com.legacy.banking.repository;

import com.legacy.banking.domain.LoanApplication;
import javax.ejb.Stateless;
import javax.persistence.EntityManager;
import javax.persistence.PersistenceContext;
import javax.persistence.TypedQuery;
import java.util.List;

/**
 * Data access EJB for LoanApplication entities.
 * Wraps JPA EntityManager operations for legacy table T_LOAN_APPLICATION.
 */
@Stateless
public class LoanApplicationRepository {

    @PersistenceContext(unitName = "bankingPU")
    private EntityManager em;

    public void save(LoanApplication application) {
        em.persist(application);
    }

    public LoanApplication findById(String applicationId) {
        return em.find(LoanApplication.class, applicationId);
    }

    public List<LoanApplication> findByAccountId(String accountId) {
        TypedQuery<LoanApplication> query = em.createQuery(
            "SELECT l FROM LoanApplication l WHERE l.accountId = :accountId", LoanApplication.class);
        query.setParameter("accountId", accountId);
        return query.getResultList();
    }

    public List<LoanApplication> findByStatus(String status) {
        TypedQuery<LoanApplication> query = em.createQuery(
            "SELECT l FROM LoanApplication l WHERE l.status = :status", LoanApplication.class);
        query.setParameter("status", status);
        return query.getResultList();
    }

    public void update(LoanApplication application) {
        em.merge(application);
    }

    public void updateStatus(String applicationId, String status, String rejectionReason) {
        LoanApplication app = em.find(LoanApplication.class, applicationId);
        if (app != null) {
            app.setStatus(status);
            if (rejectionReason != null) {
                app.setRejectionReason(rejectionReason);
            }
            em.merge(app);
        }
    }

    public void delete(String applicationId) {
        LoanApplication app = em.find(LoanApplication.class, applicationId);
        if (app != null) {
            em.remove(app);
        }
    }
}
