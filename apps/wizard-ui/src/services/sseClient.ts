import { TelemetryEvent } from '../types/telemetry';

type SSECallback = (event: TelemetryEvent) => void;
type ErrorCallback = (error: any) => void;

const isMockMode = import.meta.env.VITE_MOCK_MODE === 'true';
const apiBase = import.meta.env.VITE_API_URL || '';

export class SSEPipelineClient {
  private eventSource: EventSource | null = null;
  private runId: string | null = null;
  private retryCount: number = 0;
  private maxRetries: number = 5;
  private isManuallyClosed: boolean = false;
  private onEventCallback: SSECallback | null = null;
  private onErrorCallback: ErrorCallback | null = null;
  private mockTimer: any = null;

  connect(runId: string, onEvent: SSECallback, onError?: ErrorCallback): void {
    this.runId = runId;
    this.onEventCallback = onEvent;
    this.onErrorCallback = onError || null;
    this.isManuallyClosed = false;
    this.retryCount = 0;

    if (isMockMode) {
      this.startMockSimulation(runId);
      return;
    }

    this.initiateConnection();
  }

  private initiateConnection(): void {
    if (!this.runId || this.isManuallyClosed) return;

    if (this.eventSource) {
      this.eventSource.close();
    }

    const streamUrl = `${apiBase}/api/pipeline/runs/${this.runId}/stream`;
    console.log(`[SSE] Connecting to live telemetry stream: ${streamUrl}`);
    this.eventSource = new EventSource(streamUrl);

    this.eventSource.onopen = () => {
      console.log(`[SSE] Connected to telemetry stream for run: ${this.runId}`);
      this.retryCount = 0;
    };

    const handlePayload = (raw: string) => {
      try {
        const parsed = JSON.parse(raw);
        if (this.onEventCallback) {
          this.onEventCallback(parsed);
        }
        if (parsed.type === 'EXTRACTION_COMPLETE' || parsed.type === 'ERROR') {
          console.log(`[SSE] Terminal event reached: ${parsed.type}`);
        }
      } catch (err) {
        console.warn('[SSE] JSON parse warning:', raw, err);
      }
    };

    this.eventSource.onmessage = (event) => {
      handlePayload(event.data);
    };

    const eventTypes = [
      'RUN_STARTED',
      'PASS_STARTED',
      'TOKEN_CHUNK',
      'PASS_COMPLETED',
      'SPEC_GENERATED',
      'EXTRACTION_COMPLETE',
      'ERROR',
      'TELEMETRY_LOG',
      'HITL_GATE_REACHED',
    ];

    eventTypes.forEach((type) => {
      this.eventSource?.addEventListener(type, (event: any) => {
        handlePayload(event.data);
      });
    });

    this.eventSource.onerror = (error) => {
      if (this.isManuallyClosed) return;

      console.warn(`[SSE] Connection error on run ${this.runId}:`, error);
      if (this.onErrorCallback) {
        this.onErrorCallback(error);
      }

      this.eventSource?.close();

      if (this.retryCount < this.maxRetries) {
        this.retryCount++;
        const backoffMs = Math.min(1000 * Math.pow(2, this.retryCount), 8000);
        console.log(`[SSE] Reconnecting in ${backoffMs}ms (Attempt ${this.retryCount}/${this.maxRetries})...`);
        setTimeout(() => this.initiateConnection(), backoffMs);
      } else {
        console.warn('[SSE] Max reconnect attempts reached. Switching to mock fallback.');
        this.startMockSimulation(this.runId!);
      }
    };
  }

  private startMockSimulation(runId: string): void {
    console.log(`[SSE] Running mock telemetry simulation for run: ${runId}`);
    const simulatedEvents: TelemetryEvent[] = [
      {
        type: 'RUN_STARTED',
        run_id: runId,
        message: 'Cognitive Extraction Chain initialized for TransferManagedBean',
        timestamp: new Date().toISOString(),
      },
      {
        type: 'PASS_STARTED',
        pass_number: 1,
        name: 'Technical Decompiler',
        description: 'Strip container plumbing, JSF context, and transaction boilerplates.',
        timestamp: new Date().toISOString(),
      },
      {
        type: 'TOKEN_CHUNK',
        pass: 1,
        token: '[Pass 1] Inspecting AST slice for TransferManagedBean...\n',
        token_delta: 12,
        cumulative_tokens: 12,
      },
      {
        type: 'TOKEN_CHUNK',
        pass: 1,
        token: '[Pass 1] Stripping @ManagedBean, @SessionScoped, FacesContext navigation strings.\n',
        token_delta: 18,
        cumulative_tokens: 30,
      },
      {
        type: 'TOKEN_CHUNK',
        pass: 1,
        token: '[Pass 1] Removing container @TransactionAttribute(REQUIRED) boundaries.\n',
        token_delta: 15,
        cumulative_tokens: 45,
      },
      {
        type: 'TOKEN_CHUNK',
        pass: 1,
        token: '[Pass 1] Isolated 5 core operations and CicsMainframeGateway boundary.\n',
        token_delta: 20,
        cumulative_tokens: 65,
      },
      {
        type: 'PASS_COMPLETED',
        pass_number: 1,
        name: 'Technical Decompiler',
        latency_ms: 1240,
        tokens: 650,
      },
      {
        type: 'PASS_STARTED',
        pass_number: 2,
        name: 'Business Abstractor',
        description: 'Extract pure business invariants, validation rules, and thresholds.',
        timestamp: new Date().toISOString(),
      },
      {
        type: 'TOKEN_CHUNK',
        pass: 2,
        token: '[Pass 2] Discovered Rule BR-TRANSFER-001: Amount must be positive (amount > 0).\n',
        token_delta: 22,
        cumulative_tokens: 87,
      },
      {
        type: 'TOKEN_CHUNK',
        pass: 2,
        token: '[Pass 2] Discovered Rule BR-TRANSFER-002: Dual Account Ledger Existence.\n',
        token_delta: 20,
        cumulative_tokens: 107,
      },
      {
        type: 'TOKEN_CHUNK',
        pass: 2,
        token: '[Pass 2] Discovered Rule BR-TRANSFER-003: Sufficient Balance Invariant.\n',
        token_delta: 18,
        cumulative_tokens: 125,
      },
      {
        type: 'PASS_COMPLETED',
        pass_number: 2,
        name: 'Business Abstractor',
        latency_ms: 1860,
        tokens: 920,
      },
      {
        type: 'PASS_STARTED',
        pass_number: 3,
        name: 'Spec Formatter & Target Synthesis',
        description: 'Generate Gherkin BDD scenarios, OpenAPI 3.0 YAML, and bidirectional line mappings.',
        timestamp: new Date().toISOString(),
      },
      {
        type: 'TOKEN_CHUNK',
        pass: 3,
        token: '[Pass 3] Synthesizing Gherkin BDD Feature: Funds Transfer Operations.\n',
        token_delta: 25,
        cumulative_tokens: 150,
      },
      {
        type: 'TOKEN_CHUNK',
        pass: 3,
        token: '[Pass 3] Generating OpenAPI 3.0 YAML with RFC 7807 problem details...\n',
        token_delta: 35,
        cumulative_tokens: 185,
      },
      {
        type: 'TOKEN_CHUNK',
        pass: 3,
        token: '[Pass 3] Computing SHA-256 integrity hash: 8f4a29c1e7...\n',
        token_delta: 15,
        cumulative_tokens: 200,
      },
      {
        type: 'PASS_COMPLETED',
        pass_number: 3,
        name: 'Spec Formatter & Target Synthesis',
        latency_ms: 2150,
        tokens: 1420,
      },
      {
        type: 'SPEC_GENERATED',
        run_id: runId,
        sha256_hash: '8f4a29c1e7a5b6d8f203c4e5a1b2c3d4e5f60718293a4b5c6d7e8f901a2b3c4d',
      },
      {
        type: 'EXTRACTION_COMPLETE',
        run_id: runId,
        status: 'HITL_PENDING',
        spec_sha256: '8f4a29c1e7a5b6d8f203c4e5a1b2c3d4e5f60718293a4b5c6d7e8f901a2b3c4d',
        total_tokens: 2990,
      },
    ];

    let idx = 0;
    const interval = setInterval(() => {
      if (this.isManuallyClosed || idx >= simulatedEvents.length) {
        clearInterval(interval);
        return;
      }
      const event = simulatedEvents[idx++];
      if (this.onEventCallback) {
        this.onEventCallback(event);
      }
    }, 280);

    this.mockTimer = interval;
  }

  disconnect(): void {
    this.isManuallyClosed = true;
    if (this.mockTimer) {
      clearInterval(this.mockTimer);
      this.mockTimer = null;
    }
    if (this.eventSource) {
      console.log('[SSE] Disconnecting stream listener.');
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}

export const sseClient = new SSEPipelineClient();
