import { Component, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

export interface TransferResponse {
  correlationId: string;
  status: string;
  message: string;
  settledAt: string;
}

/**
 * Angular 18+ Standalone Microfrontend Component with Reactive Signals.
 * Traceability: Jira MOD-101 | Replaces legacy JSF /xhtml transfer form.
 */
@Component({
  selector: 'app-transfer-cockpit',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './transfer.component.html',
  styleUrls: ['./transfer.component.css']
})
export class TransferCockpitComponent {
  private fb = inject(FormBuilder);
  private http = inject(HttpClient);

  // Modern Angular Signals for reactive state
  readonly isSubmitting = signal<boolean>(false);
  readonly errorMessage = signal<string | null>(null);
  readonly transferReceipt = signal<TransferResponse | null>(null);

  readonly form = this.fb.group({
    fromAccountId: ['', [Validators.required, Validators.pattern(/^ACC-\\d{4,8}$/)]],
    toAccountId: ['', [Validators.required, Validators.pattern(/^ACC-\\d{4,8}$/)]],
    amount: [null, [Validators.required, Validators.min(0.01), Validators.max(50000)]],
    currency: ['USD']
  });

  submitTransfer(): void {
    if (this.form.invalid) return;

    this.isSubmitting.set(true);
    this.errorMessage.set(null);

    this.http.post<TransferResponse>('/api/v1/transfers', this.form.value)
      .subscribe({
        next: (receipt) => {
          this.transferReceipt.set(receipt);
          this.isSubmitting.set(false);
          this.form.reset({ currency: 'USD' });
        },
        error: (err) => {
          this.errorMessage.set(err.error?.message || 'Transaction failed. Please verify account balances.');
          this.isSubmitting.set(false);
        }
      });
  }
}
