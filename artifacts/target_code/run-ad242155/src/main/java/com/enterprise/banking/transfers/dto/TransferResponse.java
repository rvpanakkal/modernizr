package com.enterprise.banking.transfers.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import java.math.BigDecimal;
import java.time.Instant;

/**
 * Modernized Transfer Response DTO.
 * Traceability: Jira MOD-101 | Provides atomic transaction correlation receipt.
 */
@Schema(description = "Fund transfer execution receipt")
public record TransferResponse(
    @Schema(description = "Unique audit correlation tracking identifier", example = "CORR-9d8a1f2c")
    String correlationId,

    @Schema(description = "Execution status of the transfer", example = "COMPLETED")
    String status,

    @Schema(description = "Source account debited", example = "ACC-10123")
    String fromAccountId,

    @Schema(description = "Target account credited", example = "ACC-90451")
    String toAccountId,

    @Schema(description = "Settled monetary amount", example = "1250.00")
    BigDecimal amount,

    @Schema(description = "Timestamp when transfer completed in UTC")
    Instant settledAt,

    @Schema(description = "Audit message describing transaction outcome")
    String message
) {}
