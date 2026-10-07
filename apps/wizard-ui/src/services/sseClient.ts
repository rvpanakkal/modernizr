import { TelemetryEvent, GeneratedSpecification } from '../types/telemetry';

export type SSECallback = (event: TelemetryEvent) => void;
export type ErrorCallback = (error: any) => void;

export interface RunStreamHandlers {
  onToken?: (token: string, event?: TelemetryEvent) => void;
  onPassStarted?: (pass: number, event?: TelemetryEvent) => void;
  onPassCompleted?: (
    pass: number,
    stats: { latencyMs: number; tokens: number },
    event?: TelemetryEvent
  ) => void;
  onComplete?: (spec: any, event?: TelemetryEvent) => void;
  onError?: (err: any) => void;
  onEvent?: (event: TelemetryEvent) => void;
}

export interface StreamSubscription {
  close: () => void;
}

const isMockMode = import.meta.env.VITE_MOCK_MODE === 'true';
const apiBase = import.meta.env.VITE_API_URL || '';

function getMockEvents(runId: string): TelemetryEvent[] {
  return [
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
}

/**
 * Subscribes to the live Server-Sent Events stream for a specific run_id.
 * CRITICAL FIX: Explicitly terminates the EventSource upon receiving EXTRACTION_COMPLETE or ERROR
 * to eliminate browser-native automatic reconnect loops.
 */
export function subscribeToRunStream(
  runId: string,
  handlers: RunStreamHandlers
): StreamSubscription {
  if (isMockMode) {
    let mockClosed = false;
    let timer: any = null;
    const simulatedEvents = getMockEvents(runId);
    let idx = 0;

    const close = () => {
      if (mockClosed) return;
      mockClosed = true;
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    };

    timer = setInterval(() => {
      if (mockClosed || idx >= simulatedEvents.length) {
        close();
        return;
      }
      const event = simulatedEvents[idx++];
      handlers.onEvent?.(event);
      if (event.type === 'TOKEN_CHUNK' && event.token) {
        handlers.onToken?.(event.token, event);
      } else if (event.type === 'PASS_STARTED' && event.pass_number) {
        handlers.onPassStarted?.(event.pass_number, event);
      } else if (event.type === 'PASS_COMPLETED' && event.pass_number) {
        handlers.onPassCompleted?.(
          event.pass_number,
          { latencyMs: event.latency_ms || 0, tokens: event.tokens || 0 },
          event
        );
      } else if (event.type === 'EXTRACTION_COMPLETE') {
        close();
        handlers.onComplete?.(event.spec, event);
      }
    }, 280);

    return { close };
  }

  let isClosed = false;
  const streamUrl = `${apiBase}/api/pipeline/runs/${runId}/stream`;
  console.log(`[SSE] Connecting to live telemetry stream: ${streamUrl}`);
  const eventSource = new EventSource(streamUrl);

  const close = () => {
    if (isClosed) return;
    isClosed = true;
    console.log(`[SSE] Explicitly closing EventSource connection for run: ${runId}`);
    try {
      eventSource.close();
    } catch (e) {
      console.warn('[SSE] Error closing EventSource:', e);
    }
  };

  const handlePayload = (raw: string) => {
    if (isClosed) return;
    try {
      const parsed: TelemetryEvent = JSON.parse(raw);
      handlers.onEvent?.(parsed);

      if (parsed.type === 'TOKEN_CHUNK' && parsed.token) {
        handlers.onToken?.(parsed.token, parsed);
      } else if (parsed.type === 'PASS_STARTED' && parsed.pass_number) {
        handlers.onPassStarted?.(parsed.pass_number, parsed);
      } else if (parsed.type === 'PASS_COMPLETED' && parsed.pass_number) {
        handlers.onPassCompleted?.(
          parsed.pass_number,
          {
            latencyMs: parsed.latency_ms || 0,
            tokens: parsed.tokens || 0,
          },
          parsed
        );
      } else if (parsed.type === 'EXTRACTION_COMPLETE') {
        console.log(`[SSE] Terminal event EXTRACTION_COMPLETE received for ${runId}. Closing connection to avoid reconnection loop.`);
        // CRITICAL: Close EventSource immediately before server connection ends
        close();
        handlers.onComplete?.(parsed.spec, parsed);
      } else if (parsed.type === 'ERROR' || parsed.type === 'PIPELINE_ERROR') {
        console.log(`[SSE] Terminal error received for ${runId}. Closing connection.`);
        close();
        handlers.onError?.(parsed);
      }
    } catch (err) {
      console.warn('[SSE] JSON parse warning:', raw, err);
    }
  };

  eventSource.onmessage = (event) => handlePayload(event.data);

  const eventTypes = [
    'RUN_STARTED',
    'PASS_STARTED',
    'TOKEN_CHUNK',
    'PASS_COMPLETED',
    'SPEC_GENERATED',
    'EXTRACTION_COMPLETE',
    'ERROR',
    'PIPELINE_ERROR',
    'TELEMETRY_LOG',
    'HITL_GATE_REACHED',
  ];

  eventTypes.forEach((type) => {
    eventSource.addEventListener(type, (event: any) => {
      handlePayload(event.data);
    });
  });

  eventSource.onerror = (err) => {
    if (isClosed) return;
    console.warn(`[SSE] Stream closed or encountered error on run ${runId}. Terminating connection.`);
    // CRITICAL: Close EventSource so standard browser auto-reconnect does not fire
    close();
    handlers.onError?.(err);
  };

  return { close };
}

export class SSEPipelineClient {
  private eventSource: EventSource | null = null;
  private runId: string | null = null;
  private isManuallyClosed: boolean = false;
  private onEventCallback: SSECallback | null = null;
  private onErrorCallback: ErrorCallback | null = null;
  private mockTimer: any = null;

  connect(runId: string, onEvent: SSECallback, onError?: ErrorCallback): StreamSubscription {
    this.runId = runId;
    this.onEventCallback = onEvent;
    this.onErrorCallback = onError || null;
    this.isManuallyClosed = false;

    if (isMockMode) {
      this.startMockSimulation(runId);
      return { close: () => this.disconnect() };
    }

    this.initiateConnection();
    return { close: () => this.disconnect() };
  }

  private initiateConnection(): void {
    if (!this.runId || this.isManuallyClosed) return;

    if (this.eventSource) {
      this.eventSource.close();
    }

    const streamUrl = `${apiBase}/api/pipeline/runs/${this.runId}/stream`;
    console.log(`[SSEPipelineClient] Connecting to stream: ${streamUrl}`);
    this.eventSource = new EventSource(streamUrl);

    const handlePayload = (raw: string) => {
      if (this.isManuallyClosed) return;
      try {
        const parsed = JSON.parse(raw);
        if (this.onEventCallback) {
          this.onEventCallback(parsed);
        }
        if (
          parsed.type === 'EXTRACTION_COMPLETE' ||
          parsed.type === 'ERROR' ||
          parsed.type === 'PIPELINE_ERROR'
        ) {
          console.log(`[SSEPipelineClient] Terminal event reached: ${parsed.type}. Closing stream.`);
          this.disconnect();
        }
      } catch (err) {
        console.warn('[SSEPipelineClient] JSON parse warning:', raw, err);
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
      'PIPELINE_ERROR',
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

      console.warn(`[SSEPipelineClient] Stream ended or error on run ${this.runId}. Closing.`);
      this.disconnect();
      if (this.onErrorCallback) {
        this.onErrorCallback(error);
      }
    };
  }

  private startMockSimulation(runId: string): void {
    console.log(`[SSEPipelineClient] Running mock telemetry simulation for run: ${runId}`);
    const simulatedEvents = getMockEvents(runId);

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
      console.log('[SSEPipelineClient] Disconnecting and closing stream.');
      try {
        this.eventSource.close();
      } catch (e) {
        // ignore
      }
      this.eventSource = null;
    }
  }
}

export const sseClient = new SSEPipelineClient();
