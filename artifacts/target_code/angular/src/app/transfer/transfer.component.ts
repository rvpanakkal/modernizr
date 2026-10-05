import { Component, computed, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

export interface TransferRequest {
  sourceAccountId: string;
  destinationAccountId: string;
  amount: number;
}

export interface TransferResponse {
  correlationId: string;
  status: string;
  message: string;
  timestamp: string;
}

/**
 * Modernized Angular Standalone Microfrontend Component with Signals.
 * Replaces legacy JSF 2.x presentation bean (TransferManagedBean.java).
 *
 * Traceability ID: GH-101
 */
@Component({
  selector: 'app-fund-transfer',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './transfer.component.html',
  styleUrls: ['./transfer.component.css']
})
export class TransferComponent {
  private readonly http = inject(HttpClient);
  readonly jiraTrackingId = 'GH-101';
  readonly dailyCeilingLimit = 50000.00;

  // Reactive State Signals
  readonly sourceAccountId = signal<string>('');
  readonly destinationAccountId = signal<string>('');
  readonly amount = signal<number | null>(null);
  readonly submitting = signal<boolean>(false);
  readonly successResponse = signal<TransferResponse | null>(null);
  readonly errorMessage = signal<string | null>(null);

  // Computed validity guard
  readonly isValid = computed(() => {
    const src = this.sourceAccountId().trim();
    const dst = this.destinationAccountId().trim();
    const amt = this.amount();
    return src.length > 0 && dst.length > 0 && amt !== null && amt > 0 && amt <= this.dailyCeilingLimit;
  });

  readonly exceedsCeiling = computed(() => {
    const amt = this.amount();
    return amt !== null && amt > this.dailyCeilingLimit;
  });

  initiateTransfer(): void {
    if (!this.isValid()) return;

    this.submitting.set(true);
    this.errorMessage.set(null);
    this.successResponse.set(null);

    const payload: TransferRequest = {
      sourceAccountId: this.sourceAccountId(),
      destinationAccountId: this.destinationAccountId(),
      amount: this.amount()!
    };

    this.http.post<TransferResponse>('/api/v1/transfers', payload).subscribe({
      next: (resp) => {
        this.successResponse.set(resp);
        this.submitting.set(false);
      },
      error: (err) => {
        this.errorMessage.set(err.error?.message || 'Transfer failed. Check balance and account status.');
        this.submitting.set(false);
      }
    });
  }

  reset(): void {
    this.sourceAccountId.set('');
    this.destinationAccountId.set('');
    this.amount.set(null);
    this.successResponse.set(null);
    this.errorMessage.set(null);
  }
}
