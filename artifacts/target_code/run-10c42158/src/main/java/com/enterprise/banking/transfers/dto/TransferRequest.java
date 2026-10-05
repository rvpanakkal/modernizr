package com.enterprise.banking.transfers.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import java.math.BigDecimal;

/**
 * Modernized Immutable Transfer Request DTO.
 * Traceability: Jira MOD-101 | Replaces legacy JSF TransferManagedBean bindings.
 */
@Schema(description = "Fund transfer execution payload")
public record TransferRequest(
    @Schema(description = "Originating account identifier", example = "ACC-10123")
    @NotBlank(message = "Source account ID is required")
    @Pattern(regexp = "^ACC-\\d{4,8}$", message = "Invalid source account format")
    String fromAccountId,

    @Schema(description = "Destination beneficiary account identifier", example = "ACC-90451")
    @NotBlank(message = "Destination account ID is required")
    @Pattern(regexp = "^ACC-\\d{4,8}$", message = "Invalid destination account format")
    String toAccountId,

    @Schema(description = "Transfer monetary amount (positive value, ceiling $50,000.00)", example = "1250.00")
    @NotNull(message = "Transfer amount is required")
    @DecimalMin(value = "0.01", message = "Amount must be strictly greater than zero")
    @DecimalMax(value = "50000.00", message = "Amount exceeds enterprise single-transaction threshold of $50,000.00")
    BigDecimal amount,

    @Schema(description = "ISO-4217 Currency Code", example = "USD", defaultValue = "USD")
    String currency
) {
    public TransferRequest {
        currency = (currency == null || currency.isBlank()) ? "USD" : currency;
    }
}
