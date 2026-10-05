# Modernization Specification: Fund Transfer & Settlement Management

> [!IMPORTANT]
> **Domain:** `Retail Banking / Core Payments` | **Status:** `PENDING ARCHITECT APPROVAL`

## Business Summary
Modernized Fund Transfer Service replacing legacy JSF TransferManagedBean and EJB TransferProcessingService. Implements strict two-party fund movement with positive-amount validation, balance threshold enforcement, active account compliance, and atomic CICS mainframe gateway settlement (TX9021).

## Business Invariants & Domain Rules
| Rule ID | Type | Condition | Action / Outcome |
| :--- | :--- | :--- | :--- |
| `BR-001` | **VALIDATION** | Transfer request initiated with amount parameter | Validate amount > 0.00; reject with validation error if amount <= 0.00 or null |
| `BR-002` | **COMPLIANCE** | Transfer request with source account identifier | Verify account exists in AccountRepository and status == 'ACTIVE'; reject if inactive or missing |
| `BR-003` | **THRESHOLD** | Source account balance is evaluated against requested transfer amount | Verify account balance >= transfer amount; reject with insufficient funds error if balance < amount |
| `BR-004` | **THRESHOLD** | Transfer amount exceeds single-transaction or daily cumulative cap | Enforce daily transfer limit ceiling of $50,000.00 per account per business day |
| `BR-005` | **ROUTING** | All validations pass and balances verified | Dispatch atomic fund settlement to CICS mainframe gateway using transaction code TX9021 and obtain correlation ID |

## Acceptance Criteria (BDD)
### Scenario 1: Successful fund transfer with CICS settlement
```gherkin
  Given A valid and active source account 'ACC-1001' with balance $5,000.00
  Given A valid destination account 'ACC-2002' with status 'ACTIVE'
  Given A requested transfer amount of $250.00 within the $50,000.00 daily limit ceiling
  When A fund transfer is submitted from 'ACC-1001' to 'ACC-2002' for $250.00
  Then The transaction should be dispatched to CICS mainframe gateway with transaction code TX9021
  Then A settlement correlation ID must be received from the mainframe
  Then The source account 'ACC-1001' balance should be updated to $4,750.00
  Then The destination account 'ACC-2002' balance should be credited by $250.00
  Then The transaction status returned to the caller should be SUCCESS
```
*Traceability Ref:* `com.legacy.banking.service.TransferProcessingService.processTransfer`, `com.legacy.banking.gateway.CicsMainframeGateway.executeTransfer`, `com.legacy.banking.repository.AccountRepository.updateBalance`

### Scenario 2: Reject transfer when amount is zero or negative
```gherkin
  Given A registered source account 'ACC-1001'
  Given An invalid transfer amount of $0.00 or negative amount
  When The transfer request is submitted with amount <= 0.00
  Then The request must be rejected with validation error 'Transfer amount must be greater than zero'
  Then No ledger debit or credit operations must occur
  Then No external CICS mainframe dispatch must be initiated
```
*Traceability Ref:* `com.legacy.banking.service.TransferProcessingService.processTransfer`

### Scenario 3: Reject transfer when source account has insufficient balance
```gherkin
  Given An active source account 'ACC-1001' with balance $100.00
  Given A valid destination account 'ACC-2002'
  When A fund transfer of $500.00 is requested
  Then The system must reject the transaction with error 'Insufficient funds'
  Then No debit or credit operations should occur on either account
```
*Traceability Ref:* `com.legacy.banking.service.TransferProcessingService.processTransfer`, `com.legacy.banking.repository.AccountRepository.findById`

### Scenario 4: Reject transfer exceeding daily ceiling limit of $50,000.00
```gherkin
  Given An active source account 'ACC-1001' with balance $100,000.00
  Given A transfer request for $55,000.00
  When The fund transfer request is submitted
  Then The transaction must be rejected for exceeding the daily transfer limit ceiling of $50,000.00
  Then A compliance audit event must be logged
```
*Traceability Ref:* `com.legacy.banking.service.TransferProcessingService.processTransfer`, `com.legacy.banking.web.TransferManagedBean.execute`

### Scenario 5: Reject transfer when source account is not in active standing
```gherkin
  Given A source account 'ACC-1001' with status 'SUSPENDED' or 'FROZEN'
  Given A destination account 'ACC-2002' with status 'ACTIVE'
  When A fund transfer of $100.00 is submitted
  Then The transaction must be rejected with compliance error 'Source account is not active'
  Then No CICS settlement should be dispatched
```
*Traceability Ref:* `com.legacy.banking.service.TransferProcessingService.processTransfer`, `com.legacy.banking.repository.AccountRepository.findById`

## Modern Data Contract (Spring Boot / OpenAPI)
| Field | Type & Constraints |
| :--- | :--- |
| `sourceAccountId` | String - ISO 20022 compliant source account identifier |
| `destinationAccountId` | String - Target account identifier |
| `amount` | BigDecimal - Transaction monetary amount (precision 18, scale 2, strictly positive) |
| `currency` | String - 3-letter ISO 4217 currency code (default: USD) |
| `correlationId` | String - CICS host transaction correlation UUID |
| `status` | String - Settlement status (PENDING, SETTLED, REJECTED) |
| `dailyLimitCeiling` | BigDecimal - Daily account transfer threshold ($50,000.00) |

## Legacy Traceability Matrix
| Legacy Class / Method | Target Modern Responsibility |
| :--- | :--- |
| `com.legacy.banking.web.TransferManagedBean.execute` | Presentation action entry point for initiating transfer requests |
| `com.legacy.banking.service.TransferProcessingService.processTransfer` | Core transaction orchestration, validation, and settlement coordination |
| `com.legacy.banking.gateway.CicsMainframeGateway.executeTransfer` | Mainframe settlement via CICS Transaction Gateway with transaction code TX9021 |
| `com.legacy.banking.repository.AccountRepository.findById` | Account entity retrieval and existence check |
| `com.legacy.banking.repository.AccountRepository.updateBalance` | Local database ledger balance debit/credit updates post-settlement |

---
*Generated by Antigravity Legacy Modernization Factory — Code-to-Spec-to-Code Pipeline*