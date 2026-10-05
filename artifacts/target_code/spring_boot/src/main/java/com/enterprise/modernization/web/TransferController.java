package com.enterprise.modernization.web;

import com.enterprise.modernization.dto.TransferRequest;
import com.enterprise.modernization.dto.TransferResponse;
import com.enterprise.modernization.service.TransferService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * Modern REST Controller for Core Banking Fund Transfers.
 * Migrated from legacy JSF ManagedBean: com.legacy.banking.web.TransferManagedBean.
 *
 * Traceability ID: GH-101
 */
@RestController
@RequestMapping("/api/v1/transfers")
@Tag(name = "Transfers", description = "Core Banking Fund Transfer Operations")
public class TransferController {

    private static final Logger log = LoggerFactory.getLogger(TransferController.class);
    private final TransferService transferService;

    public TransferController(TransferService transferService) {
        this.transferService = transferService;
    }

    @PostMapping
    @Operation(summary = "Submit fund transfer", description = "Validates, settles, and debits/credits accounts via CICS.")
    @ApiResponse(responseCode = "200", description = "Transfer successfully settled")
    @ApiResponse(responseCode = "400", description = "Validation error or insufficient funds")
    public ResponseEntity<TransferResponse> submitTransfer(@Valid @RequestBody TransferRequest request) {
        log.info("[TransferController] [GH-101] Received transfer request from: {}", request.sourceAccountId());
        TransferResponse response = transferService.processTransfer(request);
        return ResponseEntity.ok(response);
    }
}
