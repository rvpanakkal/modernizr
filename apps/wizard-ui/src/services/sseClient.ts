type SSECallback = (event: any) => void;
type ErrorCallback = (error: any) => void;

export class SSEPipelineClient {
  private eventSource: EventSource | null = null;
  private runId: string | null = null;
  private retryCount: number = 0;
  private maxRetries: number = 5;
  private isManuallyClosed: boolean = false;
  private onEventCallback: SSECallback | null = null;
  private onErrorCallback: ErrorCallback | null = null;

  connect(runId: string, onEvent: SSECallback, onError?: ErrorCallback): void {
    this.runId = runId;
    this.onEventCallback = onEvent;
    this.onErrorCallback = onError || null;
    this.isManuallyClosed = false;
    this.retryCount = 0;

    this.initiateConnection();
  }

  private initiateConnection(): void {
    if (!this.runId || this.isManuallyClosed) return;

    if (this.eventSource) {
      this.eventSource.close();
    }

    const streamUrl = `/api/pipeline/runs/${this.runId}/stream`;
    console.log(`[SSE] Connecting to stream at ${streamUrl}`);
    this.eventSource = new EventSource(streamUrl);

    this.eventSource.onopen = () => {
      console.log(`[SSE] Connected to telemetry stream for ${this.runId}`);
      this.retryCount = 0;
    };

    this.eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        if (this.onEventCallback) {
          this.onEventCallback(parsed);
        }
        if (parsed.type === 'EXTRACTION_COMPLETE' || parsed.type === 'PIPELINE_ERROR') {
          console.log(`[SSE] Terminal event reached: ${parsed.type}`);
        }
      } catch (err) {
        console.warn('[SSE] Failed to parse event JSON:', event.data, err);
      }
    };

    // Also register specific event listeners if emitted with event names
    const eventTypes = [
      'RUN_STARTED',
      'PASS_STARTED',
      'TELEMETRY_LOG',
      'PASS_COMPLETED',
      'HITL_GATE_REACHED',
      'EXTRACTION_COMPLETE',
      'PIPELINE_ERROR',
    ];

    eventTypes.forEach((type) => {
      this.eventSource?.addEventListener(type, (event: any) => {
        try {
          const parsed = JSON.parse(event.data);
          if (this.onEventCallback) {
            this.onEventCallback(parsed);
          }
        } catch (err) {
          console.warn(`[SSE] Parse error for ${type}:`, event.data);
        }
      });
    });

    this.eventSource.onerror = (error) => {
      if (this.isManuallyClosed) return;

      console.warn(`[SSE] Connection error on ${this.runId}:`, error);
      if (this.onErrorCallback) {
        this.onErrorCallback(error);
      }

      this.eventSource?.close();

      if (this.retryCount < this.maxRetries) {
        this.retryCount++;
        const backoffMs = Math.min(1000 * Math.pow(2, this.retryCount), 10000);
        console.log(`[SSE] Reconnecting in ${backoffMs}ms (Attempt ${this.retryCount}/${this.maxRetries})...`);
        setTimeout(() => this.initiateConnection(), backoffMs);
      } else {
        console.error('[SSE] Max reconnect attempts reached.');
      }
    };
  }

  disconnect(): void {
    this.isManuallyClosed = true;
    if (this.eventSource) {
      console.log('[SSE] Disconnecting stream listener.');
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}

export const sseClient = new SSEPipelineClient();
