package com.enterprise.modernization.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;

/**
 * Modernized Transfer Request Data Transfer Object.
 * Enforces input validation rules extracted in GH-101:
 * - Positive amount (BR-001)
 * - Maximum daily ceiling limit of $50,000.00 (BR-004)
 *
 * Traceability ID: GH-101
 */
@Schema(description = "Fund transfer initiation payload")
public record TransferRequest(

    @NotBlank(message = "Source account ID is required")
    @Schema(description = "Debit source account identifier", example = "ACC-1001")
    String sourceAccountId,

    @NotBlank(message = "Destination account ID is required")
    @Schema(description = "Credit destination account identifier", example = "ACC-2002")
    String destinationAccountId,

    @NotNull(message = "Transfer amount is required")
    @DecimalMin(value = "0.01", inclusive = true, message = "Transfer amount must be strictly greater than zero")
    @DecimalMax(value = "50000.00", inclusive = true, message = "Transfer amount exceeds the daily ceiling limit of $50,000.00")
    @Schema(description = "Transfer settlement amount in USD", example = "250.00")
    BigDecimal amount

) {}
