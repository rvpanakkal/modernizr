import { GeneratedSpecification, StepHandoffReceipt } from './telemetry';

export interface HitlReviewPayload {
  spec: GeneratedSpecification;
  legacy_sources: Record<string, string>;
  receipt?: StepHandoffReceipt | Record<string, any> | null;
  run_id: string;
  jira_story_id: string;
  legacy_source: string;
  spec_sha256: string;
  status: string;
  hitl_approved: boolean;
}

export interface HitlRevisionRequest {
  run_id: string;
  reviewer_feedback?: string;
  feedback?: string;
  manual_edits?: string;
  target_pass?: number;
}

export interface HitlReviseResponse {
  status: string;
  run_id: string;
  message: string;
  revised_spec: GeneratedSpecification;
  spec_sha256: string;
  feature_name?: string;
  domain?: string;
  bdd_scenarios?: any[];
  business_rules?: any[];
  openapi_spec_yaml?: string;
  legacy_source_snapshot?: string;
  sha256_hash?: string;
}

export interface HitlApprovalRequest {
  run_id: string;
  aggregate_root: string;
  jira_epic_key: string;
  jira_story_key?: string;
  final_gherkin?: string;
  final_openapi?: string;
  approved_by?: string;
  comments?: string;
  spec_sha256?: string;
}

export interface HitlApprovalResponse {
  status: string;
  receipt_id: string;
  spec_sha256: string;
  run_id: string;
  jira_story_id: string;
  jira_status: string;
  approved_by: string;
  approval_timestamp: string;
  receipt_uri: string;
  message: string;
}
