package com.legacy.banking.gateway;

import javax.ejb.Stateless;
import java.math.BigDecimal;
import java.util.UUID;

/**
 * Integration boundary — EJB gateway to the enterprise mainframe via CICS Transaction Gateway (CTG).
 * Simulates the CICS CTG protocol. In production: uses IBM CTG JCA adapter.
 */
@Stateless
public class CicsMainframeGateway {

    private static final String CICS_ENDPOINT = "tcp://mainframe.enterprise.local:4500";
    private static final String PROGRAM_ID    = "XFER001";
    private static final int    TIMEOUT_MS    = 5_000;

    /**
     * Dispatches a fund transfer request to the CICS mainframe program XFER001.
     *
     * @param fromAccountId debit account
     * @param toAccountId   credit account
     * @param amount        settlement amount
     * @return CICS correlation ID (UUID) for audit trail
     */
    public String executeTransfer(String fromAccountId, String toAccountId, BigDecimal amount) {
        String correlationId = UUID.randomUUID().toString();

        String cicsRequest = buildCicsRequest(fromAccountId, toAccountId, amount, correlationId);
        String response    = dispatchToCics(cicsRequest);

        validateCicsResponse(response, correlationId);

        return correlationId;
    }

    public String queryAccountBalance(String accountId) {
        String correlationId = UUID.randomUUID().toString();
        String request = String.format("BAL|ACCT001|%s|%s", correlationId, accountId);
        return dispatchToCics(request);
    }

    private String buildCicsRequest(String from, String to, BigDecimal amount, String correlationId) {
        return String.format("%s|%s|%s|%s|%s",
            PROGRAM_ID, correlationId, from, to, amount.toPlainString());
    }

    private String dispatchToCics(String request) {
        // Production: IBM CTG ECI call via javax.resource.cci.Connection
        // Stub: simulate successful mainframe response
        System.out.printf("[CICS Gateway] → %s (timeout=%dms): %s%n", CICS_ENDPOINT, TIMEOUT_MS, request);
        return "OK|" + request;
    }

    private void validateCicsResponse(String response, String correlationId) {
        if (response == null || !response.startsWith("OK|")) {
            throw new RuntimeException(
                "CICS mainframe rejected transfer. CorrelationId=" + correlationId +
                " Response=" + response);
        }
    }
}
