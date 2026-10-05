package com.enterprise.modernization.service;

import com.enterprise.modernization.dto.TransferRequest;
import com.enterprise.modernization.dto.TransferResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Modern JUnit 5 BDD Acceptance Tests.
 * Directly translated from Gherkin BDD Scenarios in GeneratedSpecification.
 *
 * Traceability ID: GH-101
 */
class TransferServiceTest {

    private TransferService transferService;

    @BeforeEach
    void setUp() {
        transferService = new TransferService();
    }

    @Test
    @DisplayName("Scenario 1: Successful fund transfer with CICS settlement")
    void shouldExecuteSuccessfulTransferWithSettlement() {
        // Given a valid source account 'ACC-1001' and destination 'ACC-2002' within daily ceiling
        TransferRequest request = new TransferRequest(
                "ACC-1001",
                "ACC-2002",
                new BigDecimal("250.00")
        );

        // When
        TransferResponse response = transferService.processTransfer(request);

        // Then
        assertThat(response).isNotNull();
        assertThat(response.status()).isEqualTo("SUCCESS");
        assertThat(response.correlationId()).isNotBlank();
        assertThat(response.message()).contains("CICS");
    }

    @Test
    @DisplayName("Scenario 2: Reject transfer when amount is zero or negative")
    void shouldRejectTransferWhenAmountIsZeroOrNegative() {
        // Given
        TransferRequest requestZero = new TransferRequest("ACC-1001", "ACC-2002", BigDecimal.ZERO);
        TransferRequest requestNeg = new TransferRequest("ACC-1001", "ACC-2002", new BigDecimal("-10.00"));

        // When & Then
        assertThatThrownBy(() -> transferService.processTransfer(requestZero))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("strictly greater than zero");

        assertThatThrownBy(() -> transferService.processTransfer(requestNeg))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("strictly greater than zero");
    }

    @Test
    @DisplayName("Scenario 3: Reject transfer when source account has insufficient balance")
    void shouldRejectTransferWhenSourceHasInsufficientBalance() {
        // Given source account 'ACC-BROKE'
        TransferRequest request = new TransferRequest("ACC-BROKE", "ACC-2002", new BigDecimal("500.00"));

        // When & Then
        assertThatThrownBy(() -> transferService.processTransfer(request))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Insufficient funds");
    }

    @Test
    @DisplayName("Scenario 4: Reject transfer exceeding daily ceiling limit of $50,000.00")
    void shouldRejectTransferExceedingDailyCeilingLimitOf50000() {
        // Given transfer amount of $55,000.00 exceeding $50,000.00 ceiling
        TransferRequest request = new TransferRequest("ACC-1001", "ACC-2002", new BigDecimal("55000.00"));

        // When & Then
        assertThatThrownBy(() -> transferService.processTransfer(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("exceeds the daily limit ceiling of $50000.00");
    }

    @Test
    @DisplayName("Scenario 5: Reject transfer when source account is not in active standing")
    void shouldRejectTransferWhenAccountIsNotActive() {
        // Given source account 'ACC-INACTIVE'
        TransferRequest request = new TransferRequest("ACC-INACTIVE", "ACC-2002", new BigDecimal("100.00"));

        // When & Then
        assertThatThrownBy(() -> transferService.processTransfer(request))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("not active");
    }
}
