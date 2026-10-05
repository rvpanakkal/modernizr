package com.enterprise.banking.transfers;

import com.enterprise.banking.transfers.dto.TransferRequest;
import com.enterprise.banking.transfers.dto.TransferResponse;
import com.enterprise.banking.transfers.service.TransferProcessingService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.*;

/**
 * JUnit 5 BDD Acceptance Test Suite.
 * Traceability: Jira MOD-101 | Verifies synthesized business rules BR-001 through BR-004.
 */
@SpringBootTest
@Tag("MOD-101")
@Tag("BDD-Acceptance")
class TransferAcceptanceTest {

    @Autowired
    private TransferProcessingService transferService;

    @Test
    @DisplayName("Scenario: Successful funds transfer between active accounts")
    void testSuccessfulTransfer() {
        TransferRequest request = new TransferRequest("ACC-101", "ACC-202", new BigDecimal("500.00"), "USD");
        TransferResponse response = transferService.processTransfer(request);

        assertNotNull(response.correlationId());
        assertEquals("COMPLETED", response.status());
        assertEquals(new BigDecimal("500.00"), response.amount());
    }

    @Test
    @DisplayName("Scenario: Transfer rejected due to non-positive amount (BR-001)")
    void testRejectNonPositiveAmount() {
        TransferRequest request = new TransferRequest("ACC-101", "ACC-202", new BigDecimal("-50.00"), "USD");
        assertThrows(IllegalArgumentException.class, () -> transferService.processTransfer(request));
    }
}
