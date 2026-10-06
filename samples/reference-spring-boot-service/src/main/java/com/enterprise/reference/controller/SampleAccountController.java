package com.enterprise.reference.controller;

import com.enterprise.reference.service.AccountService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.time.Instant;

@RestController
@RequestMapping(path = "/api/v1/accounts", produces = MediaType.APPLICATION_JSON_VALUE)
public class SampleAccountController {

    private final AccountService accountService;

    public SampleAccountController(AccountService accountService) {
        this.accountService = accountService;
    }

    public record AccountResponse(
        String accountId,
        String accountHolder,
        BigDecimal balance,
        String status,
        Instant lastUpdated
    ) {}

    public record BalanceAdjustmentRequest(
        @NotBlank(message = "Adjustment reason is mandatory")
        String reason,

        @NotNull(message = "Adjustment amount is mandatory")
        @Positive(message = "Adjustment amount must be positive")
        BigDecimal amount
    ) {}

    @GetMapping("/{accountId}")
    public ResponseEntity<AccountResponse> getAccount(@PathVariable String accountId) {
        return ResponseEntity.ok(accountService.getAccount(accountId));
    }

    @PostMapping("/{accountId}/adjustments")
    public ResponseEntity<AccountResponse> adjustBalance(
            @PathVariable String accountId,
            @Valid @RequestBody BalanceAdjustmentRequest request) {
        AccountResponse response = accountService.adjustBalance(accountId, request.amount(), request.reason());
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }
}
