package com.enterprise.modernization.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import java.time.Instant;

/**
 * Modernized Transfer Response Record.
 * Traceability ID: GH-101
 */
@Schema(description = "Fund transfer settlement confirmation payload")
public record TransferResponse(

    @Schema(description = "CICS settlement correlation tracking ID", example = "550e8400-e29b-41d4-a716-446655440000")
    String correlationId,

    @Schema(description = "Settlement status code", example = "SUCCESS")
    String status,

    @Schema(description = "Descriptive outcome message", example = "Transfer settled successfully via CICS CTG")
    String message,

    @Schema(description = "ISO-8601 settlement completion timestamp")
    Instant timestamp

) {
    public static TransferResponse success(String correlationId, String message) {
        return new TransferResponse(correlationId, "SUCCESS", message, Instant.now());
    }
}
