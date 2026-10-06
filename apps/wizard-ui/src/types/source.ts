/**
 * TypeScript Contracts for Source Ingestion & File-Based LST Graph Store.
 */

export interface IngestionConfig {
  jdk_version: string;
  framework_profile: string;
  classpath_strategy: string;
}

export interface Diagnostics {
  status: string;
  graph_loaded: boolean;
  total_nodes: number;
  total_edges: number;
  total_entrypoints: number;
  resolved_type_percentage: number;
  graph_file_path: string;
  extracted_at?: string;
  sha256_digest?: string;
  entry_point_names?: string[];
}

export interface UploadResponse {
  status: string;
  classes_parsed: number;
  resolved_type_percentage: number;
  entry_points_detected: number;
  total_edges: number;
  graph_file_path: string;
  sha256_digest: string;
  extracted_at: string;
  execution_time_ms?: number;
  message?: string;
  monolith_id?: string;
  classes_count?: number;
  methods_count?: number;
  injected_fields_count?: number;
  invocations_count?: number;
  endpoints_count?: number;
  cics_gateways_count?: number;
  classes?: any[];
}

export interface IngestionStats {
  classesParsed: number;
  resolvedTypePct: number;
  entryPointCount: number;
  totalEdges: number;
  graphLoaded: boolean;
  graphFilePath: string;
  sha256Digest: string;
  extractedAt: string;
}
