/**
 * Strict TypeScript types for Batch Vertical Slice Extraction and Telemetry.
 */

export interface BatchRunRequest {
  entry_fqns: string[];
  max_depth?: number;
  tracker_type?: string;
}

export interface SliceRunSummary {
  run_id: string;
  entry_fqn: string;
  class_name: string;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  current_pass?: number | null;
  tokens_consumed: number;
  duration_ms: number;
  spec_path?: string | null;
  error_message?: string | null;
}

export interface BatchRunStatus {
  batch_id: string;
  total_slices: number;
  completed_slices: number;
  failed_slices: number;
  status: 'PROCESSING' | 'COMPLETED' | 'PARTIAL_FAILURE' | 'FAILED';
  created_at: string;
  slices: SliceRunSummary[];
}
