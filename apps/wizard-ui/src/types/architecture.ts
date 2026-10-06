/**
 * TypeScript Contracts for Target Architecture Provider Subsystem.
 * Matches backend Pydantic models in pipeline_core.schemas.architecture.
 */

export type LayeringPattern =
  | 'CONTROLLER_SERVICE_REPOSITORY'
  | 'HEXAGONAL'
  | 'CLEAN_ARCHITECTURE'
  | 'MODULAR_MONOLITH';

export interface CodePatternExemplar {
  pattern_name: string;
  target_layer: string;
  annotations_matched: string[];
  code_snippet: string;
  origin_file?: string;
}

export interface ArchUnitRule {
  rule_id: string;
  description: string;
  test_method_name: string;
  rule_code: string;
}

export interface ArchitectureProfile {
  profile_id: string;
  name: string;
  target_runtime: string;
  created_at?: string;
  base_package_pattern: string;
  layering_pattern: LayeringPattern;
  build_file_template: string;
  required_dependencies: string[];
  exemplars: CodePatternExemplar[];
  conformance_rules: ArchUnitRule[];
  sha256_hash: string;
}

export interface ProfileSummary {
  profile_id: string;
  name: string;
  target_runtime: string;
  layering_pattern: LayeringPattern;
  base_package_pattern: string;
  created_at: string;
  sha256_hash: string;
  exemplars_count: number;
  conformance_rules_count: number;
  is_active: boolean;
}

export interface HarvestReferencePayload {
  repo_path?: string;
  file?: File;
  profile_name: string;
  profile_id?: string;
}
