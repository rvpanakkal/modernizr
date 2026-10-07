/**
 * Strict TypeScript types for Step 3 Cognitive Extraction & Telemetry Streaming.
 */

export type PassStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';

export interface PassState {
  status: PassStatus;
  latencyMs: number;
  tokens: number;
  name?: string;
  description?: string;
}

export interface TraceabilityAnchor {
  legacy_file: string;
  start_line: number;
  end_line: number;
}

export interface BusinessRule {
  rule_id: string;
  name: string;
  description: string;
  severity: 'CRITICAL' | 'HIGH' | 'STANDARD' | string;
  traceability: TraceabilityAnchor;
  // Compatibility fields
  rule_type?: string;
  condition?: string;
  action_or_outcome?: string;
  legacy_refs?: string[];
}

export interface BddScenario {
  scenario_id: string;
  title: string;
  gherkin_text: string;
  linked_rule_ids: string[];
  traceability: TraceabilityAnchor;
  // Compatibility fields
  name?: string;
  given?: string[];
  when?: string;
  then?: string[];
  legacy_refs?: string[];
}

export interface GeneratedSpecification {
  run_id: string;
  feature_name: string;
  domain: string;
  entry_fqn: string;
  bdd_scenarios: BddScenario[];
  business_rules: BusinessRule[];
  openapi_spec_yaml: string;
  legacy_source_snapshot: string;
  created_at: string;
  sha256_hash: string;
  // Downstream compatibility fields
  business_summary?: string;
  scenarios?: BddScenario[];
  data_contract_fields?: Record<string, string>;
  legacy_traceability?: Record<string, string>;
  jira_story_id?: string;
  tracker_type?: string;
}

export interface StepHandoffReceipt {
  receipt_id: string;
  run_id: string;
  stage: string;
  status: 'HITL_PENDING' | 'APPROVED' | 'FAILED';
  spec_sha256: string;
  created_at: string;
}

export type TelemetryEventType =
  | 'RUN_STARTED'
  | 'PASS_STARTED'
  | 'TOKEN_CHUNK'
  | 'PASS_COMPLETED'
  | 'SPEC_GENERATED'
  | 'EXTRACTION_COMPLETE'
  | 'ERROR';

export interface TelemetryEvent {
  type: TelemetryEventType | string;
  run_id?: string;
  status?: string;
  total_tokens?: number;
  pass?: number;
  pass_number?: number;
  name?: string;
  description?: string;
  token?: string;
  token_delta?: number;
  cumulative_tokens?: number;
  latency_ms?: number;
  tokens?: number;
  spec?: GeneratedSpecification;
  spec_sha256?: string;
  sha256_hash?: string;
  error?: string;
  message?: string;
  log?: string;
  timestamp?: string;
}
