package com.enterprise.banking.transfers.controller;

import com.enterprise.banking.transfers.dto.TransferRequest;
import com.enterprise.banking.transfers.dto.TransferResponse;
import com.enterprise.banking.transfers.service.TransferProcessingService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * Spring Boot 3.5.x REST Controller.
 * Traceability: Jira MOD-101 | Replaces legacy JSF TransferManagedBean.execute() action.
 */
@RestController
@RequestMapping("/api/v1/transfers")
@Tag(name = "Fund Transfers", description = "Enterprise fund transfer and settlement API")
public class TransferController {

    private final TransferProcessingService transferService;

    public TransferController(TransferProcessingService transferService) {
        this.transferService = transferService;
    }

    @PostMapping
    @Operation(summary = "Execute fund transfer", description = "Debits source account and credits target account via corporate clearing")
    @ApiResponses({
        @ApiResponse(responseCode = "200", description = "Transfer successfully executed"),
        @ApiResponse(responseCode = "400", description = "Validation error or invalid account state"),
        @ApiResponse(responseCode = "422", description = "Insufficient funds in source account")
    })
    public ResponseEntity<TransferResponse> executeTransfer(@Valid @RequestBody TransferRequest request) {
        TransferResponse response = transferService.processTransfer(request);
        return ResponseEntity.status(HttpStatus.OK).body(response);
    }
}
