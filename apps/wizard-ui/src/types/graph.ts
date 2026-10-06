/**
 * TypeScript Contracts for Topology Discovery, NetworkX In-Memory Slicing, and Cytoscape Visualization.
 */

export type LayerType = 'PRESENTATION' | 'API' | 'SERVICE' | 'INTEGRATION' | 'DATA' | 'UTIL';

export interface EntryPoint {
  fqn: string;
  class_name: string;
  layer: LayerType;
  framework_marker: string; // e.g. "@ManagedBean", "@Path", "@RestController"
  method_count: number;
  line_count: number;
  // Backward compatibility / optional properties
  simple_name?: string;
  role?: string;
  kind?: string;
  annotations?: string[];
  injected_dependencies?: string[];
  description?: string;
}

export interface GraphNode {
  id: string; // FQN
  label: string; // Class / Component Name
  layer: LayerType;
  file_path: string;
  start_line: number;
  end_line: number;
  methods: string[];
  annotations: string[];
  // Additional / UI properties
  name?: string;
  role?: string;
  color?: string;
  source_code?: string;
  fqn?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship: 'CALLS' | 'INJECTS' | 'USES' | 'EXTENDS';
  // Additional / UI properties
  type?: string;
  label?: string;
}

export interface VerticalSliceResponse {
  entry_fqn: string;
  max_depth: number;
  total_nodes: number;
  total_edges: number;
  estimated_tokens: number;
  within_budget: boolean;
  nodes: GraphNode[];
  edges: GraphEdge[];
  aggregated_source_preview?: string;
  // Compatibility / pipeline fields
  slice_id?: string;
  execution_paths?: string[];
  component_summary?: Array<{ fqn: string; role: string; layer: string; methods_count?: number }>;
  max_tokens?: number;
  legacy_source?: string;
  raw_slice?: any;
}

// Backward-compatible alias
export type SliceResponse = VerticalSliceResponse;
