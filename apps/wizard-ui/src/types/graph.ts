/**
 * TypeScript Contracts for Topology Discovery, NetworkX In-Memory Slicing, and Cytoscape Visualization.
 */

export interface EntryPoint {
  fqn: string;
  simple_name: string;
  layer: string; // Presentation, API, Service, Integration
  role: string;
  kind: string;
  annotations: string[];
  injected_dependencies: string[];
  description: string;
}

export interface GraphNode {
  id: string;
  name: string;
  label?: string;
  fqn: string;
  role: string;
  layer: string;
  color: string;
  annotations: string[];
  methods: string[];
  file_path?: string;
  start_line?: number;
  end_line?: number;
  source_code?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string; // INJECTS, CALLS, CONNECTS_TO
  label: string;
  relationship?: string;
}

export interface SliceResponse {
  slice_id: string;
  entry_fqn: string;
  max_depth: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  execution_paths: string[];
  component_summary: Array<{ fqn: string; role: string; layer: string }>;
  estimated_tokens: number;
  max_tokens: number;
  within_budget: boolean;
  legacy_source: string;
  raw_slice: any;
}
