import { create } from 'zustand';
import {
  ArchitectureProfile,
  HarvestReferencePayload,
  ProfileSummary,
} from '../types/architecture';
import { Diagnostics, UploadResponse, IngestionStats } from '../types/source';
import {
  EntryPoint,
  GraphNode,
  GraphEdge,
  VerticalSliceResponse,
  SliceResponse,
} from '../types/graph';
import { apiClient } from '../services/api';
import { GeneratedSpecification, PassState, PassStatus, TelemetryEvent } from '../types/telemetry';
import { BatchRunStatus, SliceRunSummary } from '../types/batch';
import { sseClient } from '../services/sseClient';
import { HitlReviewPayload } from '../types/hitl';

export type EntrypointItem = EntryPoint;
export type SliceData = VerticalSliceResponse;
export type { GraphNode, GraphEdge };

export interface BusinessRule {
  rule_id: string;
  description: string;
  rule_type: string;
  condition: string;
  action_or_outcome: string;
  legacy_refs: string[];
}

export interface BddScenario {
  name: string;
  given: string[];
  when: string;
  then: string[];
  legacy_refs: string[];
}

export interface GeneratedSpec {
  feature_name: string;
  domain: string;
  business_summary: string;
  business_rules: BusinessRule[];
  scenarios: BddScenario[];
  data_contract_fields: Record<string, string>;
  legacy_traceability: Record<string, string>;
  jira_story_id?: string;
  tracker_type?: string;
  run_id?: string;
}

export interface CatalogService {
  service_id: string;
  name: string;
  domain: string;
  version: string;
  status: string;
  description: string;
  endpoints: string[];
  capabilities: string[];
  similarity_score: number;
  recommendation: string;
  adapter_strategy: string;
  overlap_fields: string[];
}

export interface CatalogMatchData {
  domain: string;
  best_match: CatalogService;
  all_candidates: CatalogService[];
  reuse_recommended: boolean;
  summary: string;
}

export interface GeneratedFile {
  path: string;
  filename: string;
  language: string;
  category: string;
  content: string;
  sha256: string;
  size_bytes: number;
}

export interface TelemetryLog {
  id: string;
  timestamp: string;
  pass_number?: number;
  log?: string;
  token_delta?: number;
  cumulative_tokens?: number;
  burn_rate?: number;
  type: string;
  raw?: any;
}

export function formatSpecGherkin(spec: GeneratedSpecification): string {
  const scenarios = spec.bdd_scenarios?.length ? spec.bdd_scenarios : (spec.scenarios || []);
  if (scenarios.length === 0) return '# No BDD scenarios extracted';

  const lines: string[] = [];
  lines.push(`Feature: ${spec.feature_name || 'Modernized Service Feature'}`);
  lines.push(`  As a banking platform service`);
  lines.push(`  I want deterministic transaction processing`);
  lines.push(`  So that account balances remain consistent and compliant\n`);

  scenarios.forEach((sc: any) => {
    if (sc.gherkin_text) {
      lines.push(sc.gherkin_text.trim());
      lines.push('');
    } else {
      lines.push(`  Scenario: ${sc.title || sc.name}`);
      sc.given?.forEach((g: string) => lines.push(`    Given ${g}`));
      if (sc.when) lines.push(`    When ${sc.when}`);
      sc.then?.forEach((t: string) => lines.push(`    Then ${t}`));
      lines.push('');
    }
  });

  return lines.join('\n');
}

interface WizardState {
  currentStep: number;
  maxCompletedStep: number;

  // Screen 1: Source Ingest & File-Based LST Store
  ingestionStats: IngestionStats | null;
  diagnostics: Diagnostics | null;
  isLoading: boolean;

  monolithInfo: {
    monolithId: string;
    classesCount: number;
    methodsCount: number;
    fieldsCount: number;
    endpointsCount: number;
    gatewaysCount: number;
    sha256Digest: string;
    extractedAt: string;
    jdkVersion: string;
    frameworkProfile: string;
    classpathStrategy: string;
  } | null;

  // Screen 2: Topology
  entrypoints: EntryPoint[];
  selectedEntrypoint: EntryPoint | null;
  selectedEntryPoint: EntryPoint | null;
  selectedEntryPoints: Set<string>;
  sliceDepth: number;
  sliceData: VerticalSliceResponse | null;
  selectedNode: GraphNode | null;
  isGraphLoading: boolean;
  graphError: string | null;

  // Screen 3: Telemetry & Batch Console
  runId: string | null;
  activeBatch: BatchRunStatus | null;
  inspectedRunId: string | null;
  currentPass: 1 | 2 | 3 | null;
  passStates: Record<1 | 2 | 3, { status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'; latencyMs: number; tokens: number }>;
  terminalLogs: string[];
  currentSpec: GeneratedSpecification | null;
  isExtracting: boolean;
  sseConnected: boolean;
  telemetryLogs: TelemetryLog[];
  activePass: number;
  passStatus: {
    pass1: 'pending' | 'running' | 'completed';
    pass2: 'pending' | 'running' | 'completed';
    pass3: 'pending' | 'running' | 'completed';
  };
  totalTokens: number;
  burnRate: number;
  isExtractionComplete: boolean;

  // Screen 4: HITL Review & Gating Cockpit
  hitlData: HitlReviewPayload | null;
  specData: GeneratedSpec | null;
  legacySource: string;
  activeLegacyFile: string;
  specSha256: string;
  highlightedLines: [number, number] | null;
  activeScenarioName: string | null;
  activeScenarioId: string | null;
  hitlApproved: boolean;
  approvedBy: string;
  jiraStoryId: string;
  aggregateRoot: string;
  jiraEpicKey: string;
  jiraStoryKey: string;
  reviewFeedback: string;
  isRevising: boolean;
  isApproving: boolean;
  hitlError: string | null;
  editableSpecGherkin: string;
  editableSpecOpenApi: string;

  // Screen 5: Synthesis
  catalogMatch: CatalogMatchData | null;
  targetStack: string;
  generatedFiles: GeneratedFile[];
  selectedFile: GeneratedFile | null;

  // Target Architecture Profile Subsystem
  architectureProfiles: ArchitectureProfile[];
  activeProfile: ArchitectureProfile | null;
  isLoadingProfile: boolean;

  // Actions
  uploadSource: (formData: FormData) => Promise<UploadResponse>;
  fetchDiagnostics: () => Promise<Diagnostics | void>;
  fetchEntrypoints: () => Promise<EntryPoint[]>;
  fetchEntryPoints: () => Promise<EntryPoint[]>;
  selectEntryPoint: (entry: EntryPoint) => Promise<void> | void;
  fetchSliceTopology: (entryFqn?: string, depth?: number) => Promise<void>;
  proceedToExtraction: () => Promise<void>;
  extractAndProceed: () => Promise<void>;
  proceedToHitlReview: () => void;
  startExtraction: (entryFqn?: string, maxDepth?: number) => Promise<void>;
  startBatchExtraction: () => Promise<void>;
  toggleEntryPointSelection: (fqn: string) => void;
  selectAllEntryPoints: (fqns: string[]) => void;
  clearEntryPointSelection: () => void;
  setInspectedRunId: (runId: string) => void;
  pollBatchStatus: (batchId: string) => Promise<void>;
  appendTerminalToken: (token: string) => void;
  setPassCompleted: (passNumber: 1 | 2 | 3, stats: { latencyMs: number; tokens: number }) => void;
  updatePassState: (pass: number, status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED', stats?: { latencyMs?: number; tokens?: number }) => void;
  completeExtraction: (spec: GeneratedSpecification) => void;
  handleExtractionComplete: (spec: GeneratedSpecification) => void;
  handleExtractionError: (err: any) => void;
  clearTerminalLogs: () => void;

  // Screen 4 HITL Actions
  fetchHitlData: (runId?: string) => Promise<void>;
  setActiveLegacyFile: (fileName: string) => void;
  selectScenario: (scenarioIdOrTitle: string) => void;
  setAggregateRoot: (root: string) => void;
  setJiraEpicKey: (key: string) => void;
  setJiraStoryKey: (key: string) => void;
  setReviewFeedback: (feedback: string) => void;
  setEditableSpecGherkin: (text: string) => void;
  setEditableSpecOpenApi: (text: string) => void;
  submitAiRevision: (feedbackText?: string, manualEdits?: string) => Promise<void>;
  approveAndProceed: () => Promise<void>;

  setStep: (step: number) => void;
  setMonolithInfo: (info: any) => void;
  setEntrypoints: (entries: EntryPoint[]) => void;
  selectEntrypoint: (entry: EntryPoint) => void;
  setSliceDepth: (depth: number) => void;
  setSliceData: (slice: SliceData) => void;
  setSelectedNode: (node: GraphNode | null) => void;
  setRunId: (runId: string) => void;
  setSseConnected: (status: boolean) => void;
  appendTelemetry: (event: any) => void;
  resetTelemetry: () => void;
  setSpecData: (spec: GeneratedSpec, source: string, sha: string, approved?: boolean) => void;
  updateSpecData: (spec: GeneratedSpec, sha: string) => void;
  setHighlightedLines: (range: [number, number] | null) => void;
  setActiveScenarioName: (name: string | null) => void;
  setHitlApproved: (approved: boolean, approver?: string) => void;
  setCatalogMatch: (match: CatalogMatchData) => void;
  setTargetStack: (stack: string) => void;
  setGeneratedFiles: (files: GeneratedFile[]) => void;
  setSelectedFile: (file: GeneratedFile | null) => void;
  fetchArchitectureProfiles: () => Promise<void>;
  setActiveProfile: (profileId: string) => Promise<void>;
  uploadReferenceMicroservice: (payload: HarvestReferencePayload) => Promise<ArchitectureProfile>;
  resetWizard: () => void;
}

export const useWizardStore = create<WizardState>((set, get) => ({
  currentStep: 1,
  maxCompletedStep: 1,

  ingestionStats: null,
  diagnostics: null,
  isLoading: false,

  monolithInfo: null,

  // Architecture Profile State
  architectureProfiles: [],
  activeProfile: null,
  isLoadingProfile: false,

  entrypoints: [],
  selectedEntrypoint: null,
  selectedEntryPoint: null,
  selectedEntryPoints: new Set<string>(),
  sliceDepth: 5,
  sliceData: null,
  selectedNode: null,
  isGraphLoading: false,
  graphError: null,

  runId: null,
  activeBatch: null,
  inspectedRunId: null,
  currentPass: null,
  passStates: {
    1: { status: 'PENDING', latencyMs: 0, tokens: 0 },
    2: { status: 'PENDING', latencyMs: 0, tokens: 0 },
    3: { status: 'PENDING', latencyMs: 0, tokens: 0 },
  },
  terminalLogs: [],
  currentSpec: null,
  isExtracting: false,
  sseConnected: false,
  telemetryLogs: [],
  activePass: 1,
  passStatus: {
    pass1: 'pending',
    pass2: 'pending',
    pass3: 'pending',
  },
  totalTokens: 0,
  burnRate: 0,
  isExtractionComplete: false,

  hitlData: null,
  specData: null,
  legacySource: '',
  activeLegacyFile: 'TransferProcessingService.java',
  specSha256: '',
  highlightedLines: null,
  activeScenarioName: null,
  activeScenarioId: null,
  hitlApproved: false,
  approvedBy: 'Enterprise Lead Architect',
  jiraStoryId: 'MOD-101',
  aggregateRoot: 'Account',
  jiraEpicKey: 'MOD-EPIC-12',
  jiraStoryKey: 'MOD-101',
  reviewFeedback: '',
  isRevising: false,
  isApproving: false,
  hitlError: null,
  editableSpecGherkin: '',
  editableSpecOpenApi: '',

  catalogMatch: null,
  targetStack: 'spring_boot_3_5',
  generatedFiles: [],
  selectedFile: null,

  uploadSource: async (formData: FormData): Promise<UploadResponse> => {
    set({ isLoading: true });
    try {
      const res = await apiClient.uploadSource(formData);
      const classesParsed = res.classes_parsed ?? res.classes_count ?? 15;
      const entryPointsDetected = res.entry_points_detected ?? res.endpoints_count ?? 3;
      const resolvedTypePct = res.resolved_type_percentage ?? 98.4;
      const totalEdges = res.total_edges ?? 24;
      const sha256Digest = res.sha256_digest || '';
      const graphFilePath = res.graph_file_path || 'artifacts/metadata/lst_graph.json';

      set({
        ingestionStats: {
          classesParsed,
          resolvedTypePct,
          entryPointCount: entryPointsDetected,
          totalEdges,
          graphLoaded: true,
          graphFilePath,
          sha256Digest,
          extractedAt: res.extracted_at,
        },
        monolithInfo: {
          monolithId: res.monolith_id || 'legacy-banking-monolith',
          classesCount: classesParsed,
          methodsCount: res.methods_count ?? 142,
          fieldsCount: res.injected_fields_count ?? 16,
          endpointsCount: entryPointsDetected,
          gatewaysCount: res.cics_gateways_count ?? 3,
          sha256Digest,
          extractedAt: res.extracted_at,
          jdkVersion: (formData.get('jdk_version') as string) || '8',
          frameworkProfile: (formData.get('framework_profile') as string) || 'JAVA_EE_6_JSF',
          classpathStrategy: (formData.get('classpath_strategy') as string) || 'AI_SYNTHETIC_STUBS',
        },
        maxCompletedStep: Math.max(get().maxCompletedStep, 1),
      });

      // Auto-fetch entry points and prime slice
      await get().fetchEntryPoints();
      return res;
    } finally {
      set({ isLoading: false });
    }
  },

  fetchDiagnostics: async (): Promise<Diagnostics | void> => {
    try {
      const diag = await apiClient.getDiagnostics();
      set({ diagnostics: diag });
      if (diag.graph_loaded) {
        set((state) => ({
          ingestionStats: state.ingestionStats || {
            classesParsed: diag.total_nodes,
            resolvedTypePct: diag.resolved_type_percentage,
            entryPointCount: diag.total_entrypoints,
            totalEdges: diag.total_edges,
            graphLoaded: true,
            graphFilePath: diag.graph_file_path,
            sha256Digest: diag.sha256_digest || '',
            extractedAt: diag.extracted_at || '',
          },
        }));
      }
      return diag;
    } catch (err) {
      console.warn('Failed to fetch diagnostics:', err);
    }
  },

  fetchEntrypoints: async (): Promise<EntryPoint[]> => {
    set({ isGraphLoading: true, graphError: null, isLoading: true });
    try {
      const list = await apiClient.getEntrypoints();
      set({ entrypoints: list, graphError: null });
      if (list.length > 0) {
        const active = get().selectedEntryPoint || list[0];
        set({ selectedEntryPoint: active, selectedEntrypoint: active });
        await get().fetchSliceTopology(active.fqn, get().sliceDepth);
      } else {
        set({
          selectedEntryPoint: null,
          selectedEntrypoint: null,
          sliceData: null,
          selectedNode: null,
        });
      }
      return list;
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || 'Failed to fetch entry points from graph store.';
      console.error('Failed to fetch entry points:', err);
      set({ graphError: errorMsg });
      return [];
    } finally {
      set({ isGraphLoading: false, isLoading: false });
    }
  },

  fetchEntryPoints: async (): Promise<EntryPoint[]> => {
    return get().fetchEntrypoints();
  },

  selectEntryPoint: async (entry: EntryPoint): Promise<void> => {
    set({
      selectedEntryPoint: entry,
      selectedEntrypoint: entry,
      selectedNode: null,
      graphError: null,
    });
    await get().fetchSliceTopology(entry.fqn, get().sliceDepth);
  },

  selectEntrypoint: (entry: EntryPoint) => {
    get().selectEntryPoint(entry);
  },

  setSliceDepth: (depth: number) => {
    set({ sliceDepth: depth });
    const current = get().selectedEntryPoint;
    if (current) {
      get().fetchSliceTopology(current.fqn, depth);
    }
  },

  fetchSliceTopology: async (entryFqn?: string, depth?: number): Promise<void> => {
    const fqn = entryFqn || get().selectedEntryPoint?.fqn;
    const currentDepth = depth ?? get().sliceDepth;
    if (!fqn) return;

    set({ isGraphLoading: true, graphError: null, isLoading: true });
    try {
      const slice = await apiClient.getSlice(fqn, currentDepth);
      set({
        sliceData: slice,
        selectedNode: slice.nodes && slice.nodes.length > 0 ? slice.nodes[0] : null,
        graphError: null,
        maxCompletedStep: Math.max(get().maxCompletedStep, 2),
      });
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || `Failed to extract vertical slice for ${fqn}`;
      console.error('Failed to fetch vertical slice:', err);
      set({ graphError: errorMsg });
    } finally {
      set({ isGraphLoading: false, isLoading: false });
    }
  },

  startExtraction: async (entryFqn?: string, depth?: number): Promise<void> => {
    const entry = get().selectedEntryPoint;
    const fqn = entryFqn || entry?.fqn || 'com.legacy.banking.web.TransferManagedBean';
    const currentDepth = depth ?? get().sliceDepth ?? 5;
    const slice = get().sliceData;
    const slicePayload = slice?.raw_slice && Object.keys(slice.raw_slice).length > 0 ? slice.raw_slice : slice;

    set({
      isLoading: true,
      isExtracting: true,
      currentPass: 1,
      passStates: {
        1: { status: 'RUNNING', latencyMs: 0, tokens: 0 },
        2: { status: 'PENDING', latencyMs: 0, tokens: 0 },
        3: { status: 'PENDING', latencyMs: 0, tokens: 0 },
      },
      terminalLogs: [],
      currentStep: 3,
      maxCompletedStep: Math.max(get().maxCompletedStep, 2),
    });
    get().resetTelemetry();

    try {
      const res = await apiClient.startPipelineRun(fqn, slicePayload, 'jira');
      const runId = res.run_id;
      set({ runId, isLoading: false, isExtracting: true });
    } catch (err) {
      console.warn('Failed to start pipeline run through API; falling back to simulator:', err);
      set({ isLoading: false });
      const fallbackRunId = `run-${Math.random().toString(36).substring(2, 9)}`;
      set({ runId: fallbackRunId, isExtracting: true });
    }
  },

  appendTerminalToken: (token: string) => {
    set((state) => ({
      terminalLogs: [...state.terminalLogs, token],
    }));
  },

  setPassCompleted: (passNumber: 1 | 2 | 3, stats: { latencyMs: number; tokens: number }) => {
    set((state) => ({
      passStates: {
        ...state.passStates,
        [passNumber]: { status: 'COMPLETED', latencyMs: stats.latencyMs, tokens: stats.tokens },
      },
    }));
  },

  updatePassState: (
    pass: number,
    status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
    stats?: { latencyMs?: number; tokens?: number }
  ) => {
    const pNum = pass as 1 | 2 | 3;
    set((state) => ({
      currentPass: status === 'RUNNING' ? pNum : state.currentPass,
      passStates: {
        ...state.passStates,
        [pNum]: {
          status,
          latencyMs: stats?.latencyMs ?? state.passStates[pNum].latencyMs,
          tokens: stats?.tokens ?? state.passStates[pNum].tokens,
        },
      },
    }));
  },

  handleExtractionComplete: (spec: GeneratedSpecification) => {
    get().completeExtraction(spec);
  },

  handleExtractionError: (err: any) => {
    console.warn('[wizardStore] Extraction error:', err);
    set({ isExtracting: false });
  },

  completeExtraction: (spec: GeneratedSpecification) => {
    const rawSpec: any = spec;
    const businessRules: BusinessRule[] = (spec.business_rules || []).map((r: any) => ({
      rule_id: r.rule_id,
      description: r.description || r.name,
      rule_type: r.severity || r.rule_type || 'VALIDATION',
      condition: r.condition || '',
      action_or_outcome: r.action_or_outcome || '',
      legacy_refs: r.legacy_refs || (r.traceability ? [`${r.traceability.legacy_file}:L${r.traceability.start_line}-L${r.traceability.end_line}`] : []),
    }));

    const scenarios: BddScenario[] = (spec.bdd_scenarios || (spec as any).scenarios || []).map((s: any) => ({
      name: s.title || s.name || '',
      given: s.given || (s.gherkin_text ? [s.gherkin_text] : []),
      when: s.when || '',
      then: s.then || [],
      legacy_refs: s.legacy_refs || (s.traceability ? [`${s.traceability.legacy_file}:L${s.traceability.start_line}-L${s.traceability.end_line}`] : []),
    }));

    const adaptedSpec: GeneratedSpec = {
      feature_name: spec.feature_name,
      domain: spec.domain,
      business_summary: spec.business_summary || '',
      business_rules: businessRules,
      scenarios: scenarios,
      data_contract_fields: spec.data_contract_fields || {},
      legacy_traceability: spec.legacy_traceability || {},
      jira_story_id: spec.jira_story_id || 'MOD-101',
      run_id: spec.run_id,
    };

    set({
      currentSpec: spec,
      specData: adaptedSpec,
      specSha256: spec.sha256_hash,
      legacySource: spec.legacy_source_snapshot || '',
      isExtracting: false,
      isExtractionComplete: true,
      maxCompletedStep: Math.max(get().maxCompletedStep, 3),
    });
  },

  clearTerminalLogs: () => {
    set({ terminalLogs: [] });
  },

  toggleEntryPointSelection: (fqn: string) => {
    const current = new Set(get().selectedEntryPoints);
    if (current.has(fqn)) {
      current.delete(fqn);
    } else {
      current.add(fqn);
    }
    set({ selectedEntryPoints: current });
  },

  selectAllEntryPoints: (fqns: string[]) => {
    set({ selectedEntryPoints: new Set(fqns) });
  },

  clearEntryPointSelection: () => {
    set({ selectedEntryPoints: new Set() });
  },

  startBatchExtraction: async (): Promise<void> => {
    const selectedFqns = Array.from(get().selectedEntryPoints);
    const fqnsToRun =
      selectedFqns.length > 0
        ? selectedFqns
        : get().selectedEntryPoint
        ? [get().selectedEntryPoint!.fqn]
        : [];

    if (fqnsToRun.length === 0) return;

    set({
      isLoading: true,
      isExtracting: true,
      currentStep: 3,
      maxCompletedStep: Math.max(get().maxCompletedStep, 2),
    });
    get().resetTelemetry();

    try {
      const batchStatus = await apiClient.startBatchRun(fqnsToRun, get().sliceDepth, 'jira');
      const firstRunId = batchStatus.slices.length > 0 ? batchStatus.slices[0].run_id : null;

      set({
        activeBatch: batchStatus,
        inspectedRunId: firstRunId,
        runId: firstRunId,
        isLoading: false,
      });

      if (firstRunId) {
        get().setInspectedRunId(firstRunId);
      }

      get().pollBatchStatus(batchStatus.batch_id);
    } catch (err) {
      console.warn('Failed to start batch extraction:', err);
      set({ isLoading: false });
    }
  },

  setInspectedRunId: (runId: string) => {
    set({
      inspectedRunId: runId,
      runId: runId,
      terminalLogs: [],
      currentPass: 1,
      passStates: {
        1: { status: 'PENDING', latencyMs: 0, tokens: 0 },
        2: { status: 'PENDING', latencyMs: 0, tokens: 0 },
        3: { status: 'PENDING', latencyMs: 0, tokens: 0 },
      },
    });
  },

  pollBatchStatus: async (batchId: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const updated = await apiClient.getBatchStatus(batchId);
        set({ activeBatch: updated });

        if (
          updated.status === 'COMPLETED' ||
          updated.status === 'PARTIAL_FAILURE' ||
          updated.status === 'FAILED'
        ) {
          clearInterval(pollInterval);
          set({
            isExtracting: false,
            isExtractionComplete: true,
            maxCompletedStep: Math.max(get().maxCompletedStep, 3),
          });
        }
      } catch (err) {
        console.warn('[wizardStore] Batch polling error:', err);
      }
    }, 1500);
  },

  proceedToExtraction: async (): Promise<void> => {
    return get().startExtraction();
  },

  extractAndProceed: async (): Promise<void> => {
    return get().startExtraction();
  },

  proceedToHitlReview: () => {
    set({
      currentStep: 4,
      maxCompletedStep: Math.max(get().maxCompletedStep, 3),
    });
  },

  setStep: (step: number) => {
    const current = get().currentStep;
    const maxCompleted = get().maxCompletedStep;
    // Gating: cannot jump past maxCompletedStep + 1
    if (step <= maxCompleted + 1 && step >= 1 && step <= 5) {
      set({ currentStep: step });
    }
  },

  setMonolithInfo: (info: any) => {
    set({
      monolithInfo: info,
      maxCompletedStep: Math.max(get().maxCompletedStep, 1),
    });
  },

  setEntrypoints: (entries: EntryPoint[]) => {
    set({ entrypoints: entries });
    if (entries.length > 0 && !get().selectedEntryPoint) {
      set({ selectedEntryPoint: entries[0], selectedEntrypoint: entries[0] });
    }
  },

  setSliceData: (slice: SliceData) => {
    set({
      sliceData: slice,
      selectedNode: slice.nodes[0] || null,
      maxCompletedStep: Math.max(get().maxCompletedStep, 2),
    });
  },

  setSelectedNode: (node: GraphNode | null) => {
    set({ selectedNode: node });
  },

  setRunId: (runId: string) => {
    set({ runId, maxCompletedStep: Math.max(get().maxCompletedStep, 2) });
  },

  setSseConnected: (status: boolean) => {
    set({ sseConnected: status });
  },

  appendTelemetry: (event: any) => {
    const state = get();
    const type = event.type || 'LOG';
    const newLog: TelemetryLog = {
      id: Math.random().toString(36).substring(2, 9),
      timestamp: event.timestamp || new Date().toISOString(),
      pass_number: event.pass_number,
      log: event.log || event.message,
      token_delta: event.token_delta,
      cumulative_tokens: event.cumulative_tokens,
      burn_rate: event.burn_rate,
      type,
      raw: event,
    };

    const nextLogs = [...state.telemetryLogs, newLog];
    const passStatus = { ...state.passStatus };
    let activePass = state.activePass;
    let isExtractionComplete = state.isExtractionComplete;
    let totalTokens = event.cumulative_tokens ?? state.totalTokens;
    let burnRate = event.burn_rate ?? state.burnRate;

    if (type === 'PASS_STARTED') {
      activePass = event.pass_number;
      if (event.pass_number === 1) passStatus.pass1 = 'running';
      if (event.pass_number === 2) passStatus.pass2 = 'running';
      if (event.pass_number === 3) passStatus.pass3 = 'running';
    } else if (type === 'PASS_COMPLETED') {
      if (event.pass_number === 1) passStatus.pass1 = 'completed';
      if (event.pass_number === 2) passStatus.pass2 = 'completed';
      if (event.pass_number === 3) passStatus.pass3 = 'completed';
    } else if (type === 'EXTRACTION_COMPLETE') {
      isExtractionComplete = true;
      passStatus.pass1 = 'completed';
      passStatus.pass2 = 'completed';
      passStatus.pass3 = 'completed';
      set({ maxCompletedStep: Math.max(state.maxCompletedStep, 3) });
    }

    set({
      telemetryLogs: nextLogs,
      passStatus,
      activePass,
      totalTokens,
      burnRate,
      isExtractionComplete,
    });
  },

  resetTelemetry: () => {
    set({
      currentPass: null,
      passStates: {
        1: { status: 'PENDING', latencyMs: 0, tokens: 0 },
        2: { status: 'PENDING', latencyMs: 0, tokens: 0 },
        3: { status: 'PENDING', latencyMs: 0, tokens: 0 },
      },
      terminalLogs: [],
      currentSpec: null,
      isExtracting: false,
      telemetryLogs: [],
      activePass: 1,
      passStatus: { pass1: 'pending', pass2: 'pending', pass3: 'pending' },
      totalTokens: 0,
      burnRate: 0,
      isExtractionComplete: false,
    });
  },

  setSpecData: (spec: GeneratedSpec, source: string, sha: string, approved: boolean = false) => {
    set({
      specData: spec,
      legacySource: source,
      specSha256: sha,
      hitlApproved: approved,
      jiraStoryId: spec.jira_story_id || 'MOD-101',
    });
  },

  updateSpecData: (spec: GeneratedSpec, sha: string) => {
    set({
      specData: spec,
      specSha256: sha,
    });
  },

  setHighlightedLines: (range: [number, number] | null) => {
    set({ highlightedLines: range });
  },

  setActiveScenarioName: (name: string | null) => {
    set({ activeScenarioName: name });
  },

  setHitlApproved: (approved: boolean, approver?: string) => {
    set({
      hitlApproved: approved,
      approvedBy: approver || 'Enterprise Lead Architect',
      maxCompletedStep: Math.max(get().maxCompletedStep, 4),
    });
  },

  fetchHitlData: async (runIdParam?: string) => {
    const activeRunId = runIdParam || get().runId || 'run-canonical';
    try {
      const data = await apiClient.getHitlReviewData(activeRunId);
      const spec = data.spec;
      const gherkinText = formatSpecGherkin(spec);
      const openApiText = spec.openapi_spec_yaml || '';

      const legacyFiles = Object.keys(data.legacy_sources || {});
      const activeLegacyFile = legacyFiles.length > 0 ? legacyFiles[0] : 'TransferProcessingService.java';
      const initialSource = data.legacy_sources?.[activeLegacyFile] || data.legacy_source || '';

      const scenarios = spec.bdd_scenarios?.length ? spec.bdd_scenarios : (spec.scenarios || []);
      const firstScenario = scenarios[0];
      const initialHighlight: [number, number] | null = firstScenario?.traceability
        ? [firstScenario.traceability.start_line, firstScenario.traceability.end_line]
        : null;

      set({
        hitlData: data,
        currentSpec: spec,
        specData: spec as any,
        runId: data.run_id,
        specSha256: data.spec_sha256,
        jiraStoryId: data.jira_story_id || 'MOD-101',
        jiraStoryKey: data.jira_story_id || 'MOD-101',
        hitlApproved: data.hitl_approved,
        legacySource: initialSource,
        activeLegacyFile,
        editableSpecGherkin: gherkinText,
        editableSpecOpenApi: openApiText,
        activeScenarioId: firstScenario ? (firstScenario.scenario_id || firstScenario.title || (firstScenario as any).name) : null,
        activeScenarioName: firstScenario ? (firstScenario.title || (firstScenario as any).name) : null,
        highlightedLines: initialHighlight,
        hitlError: null,
      });
    } catch (err: any) {
      console.error('[wizardStore] fetchHitlData error:', err);
      const errorMsg = err?.response?.data?.detail || err?.message || 'Failed to fetch HITL review payload';
      set({ hitlError: errorMsg });
    }
  },

  setActiveLegacyFile: (fileName: string) => {
    const data = get().hitlData;
    const source = data?.legacy_sources?.[fileName] || '';
    set({
      activeLegacyFile: fileName,
      legacySource: source,
    });
  },

  selectScenario: (scenarioIdOrTitle: string) => {
    const spec = get().currentSpec || (get().hitlData?.spec as GeneratedSpecification);
    if (!spec) return;

    const scenarios = spec.bdd_scenarios?.length ? spec.bdd_scenarios : (spec.scenarios || []);
    const match = scenarios.find(
      (s: any) =>
        s.scenario_id === scenarioIdOrTitle ||
        s.title === scenarioIdOrTitle ||
        s.name === scenarioIdOrTitle
    );

    if (match) {
      const scenarioId = match.scenario_id || match.title || (match as any).name;
      const scenarioTitle = match.title || (match as any).name;
      let highlight: [number, number] | null = null;
      let targetFile = get().activeLegacyFile;

      if (match.traceability) {
        highlight = [match.traceability.start_line, match.traceability.end_line];
        if (match.traceability.legacy_file) {
          const parts = match.traceability.legacy_file.split(/[\/\\]/);
          const baseName = parts[parts.length - 1];
          if (get().hitlData?.legacy_sources?.[baseName]) {
            targetFile = baseName;
          }
        }
      }

      const legacySource = get().hitlData?.legacy_sources?.[targetFile] || get().legacySource;

      set({
        activeScenarioId: scenarioId,
        activeScenarioName: scenarioTitle,
        highlightedLines: highlight,
        activeLegacyFile: targetFile,
        legacySource,
      });
    }
  },

  setAggregateRoot: (root: string) => set({ aggregateRoot: root }),
  setJiraEpicKey: (key: string) => set({ jiraEpicKey: key }),
  setJiraStoryKey: (key: string) => set({ jiraStoryKey: key }),
  setReviewFeedback: (feedback: string) => set({ reviewFeedback: feedback }),
  setEditableSpecGherkin: (text: string) => set({ editableSpecGherkin: text }),
  setEditableSpecOpenApi: (text: string) => set({ editableSpecOpenApi: text }),

  submitAiRevision: async (feedbackText?: string, manualEdits?: string) => {
    const feedback = feedbackText || get().reviewFeedback;
    if (!feedback || !feedback.trim()) {
      set({ hitlError: 'Reviewer feedback is required before triggering revision.' });
      return;
    }

    const activeRunId = get().runId || 'run-canonical';
    set({ isRevising: true, hitlError: null });

    try {
      const res = await apiClient.reviseSpecWithAi({
        run_id: activeRunId,
        reviewer_feedback: feedback,
        manual_edits: manualEdits || get().editableSpecGherkin,
        target_pass: 2,
      });

      const revised = res.revised_spec;
      const gherkinText = formatSpecGherkin(revised);
      const openApiText = revised.openapi_spec_yaml || res.openapi_spec_yaml || '';

      const existingData = get().hitlData;
      const updatedHitlData: HitlReviewPayload = existingData
        ? {
            ...existingData,
            spec: revised,
            spec_sha256: res.spec_sha256,
          }
        : {
            spec: revised,
            legacy_sources: { [get().activeLegacyFile || 'TransferProcessingService.java']: get().legacySource },
            run_id: activeRunId,
            jira_story_id: revised.jira_story_id || get().jiraStoryId,
            legacy_source: get().legacySource,
            spec_sha256: res.spec_sha256,
            status: 'REVISED',
            hitl_approved: false,
          };

      const scenarios = revised.bdd_scenarios?.length ? revised.bdd_scenarios : (revised.scenarios || []);
      const firstScenario = scenarios[0];

      set({
        isRevising: false,
        hitlData: updatedHitlData,
        currentSpec: revised,
        specData: revised as any,
        specSha256: res.spec_sha256,
        editableSpecGherkin: gherkinText,
        editableSpecOpenApi: openApiText,
        reviewFeedback: '',
        activeScenarioId: firstScenario ? (firstScenario.scenario_id || firstScenario.title || (firstScenario as any).name) : null,
        activeScenarioName: firstScenario ? (firstScenario.title || (firstScenario as any).name) : null,
        highlightedLines: firstScenario?.traceability ? [firstScenario.traceability.start_line, firstScenario.traceability.end_line] : null,
      });
    } catch (err: any) {
      console.error('[wizardStore] submitAiRevision error:', err);
      const errorMsg = err?.response?.data?.detail || err?.message || 'AI Revision failed';
      set({ isRevising: false, hitlError: errorMsg });
      throw err;
    }
  },

  approveAndProceed: async () => {
    const activeRunId = get().runId || 'run-canonical';
    set({ isApproving: true, hitlError: null });

    try {
      const res = await apiClient.approveHitlSpec({
        run_id: activeRunId,
        aggregate_root: get().aggregateRoot || 'Account',
        jira_epic_key: get().jiraEpicKey || 'MOD-EPIC-12',
        jira_story_key: get().jiraStoryKey || get().jiraStoryId || 'MOD-101',
        final_gherkin: get().editableSpecGherkin,
        final_openapi: get().editableSpecOpenApi,
        approved_by: get().approvedBy || 'Enterprise Lead Architect',
        spec_sha256: get().specSha256,
      });

      set({
        isApproving: false,
        hitlApproved: true,
        approvedBy: res.approved_by,
        maxCompletedStep: Math.max(get().maxCompletedStep, 4),
        currentStep: 5,
      });
    } catch (err: any) {
      console.error('[wizardStore] approveAndProceed error:', err);
      const errorMsg = err?.response?.data?.detail || err?.message || 'Approval failed';
      set({ isApproving: false, hitlError: errorMsg });
      throw err;
    }
  },

  setCatalogMatch: (match: CatalogMatchData) => {
    set({ catalogMatch: match });
  },

  setTargetStack: (stack: string) => {
    set({ targetStack: stack });
  },

  setGeneratedFiles: (files: GeneratedFile[]) => {
    set({
      generatedFiles: files,
      selectedFile: files[0] || null,
      maxCompletedStep: 5,
    });
  },

  setSelectedFile: (file: GeneratedFile | null) => {
    set({ selectedFile: file });
  },

  fetchArchitectureProfiles: async () => {
    set({ isLoadingProfile: true });
    try {
      const summaries = await apiClient.getArchitectureProfiles();
      const fullProfiles: ArchitectureProfile[] = (
        await Promise.all(
          summaries.map(async (s) => {
            try {
              return await apiClient.getArchitectureProfile(s.profile_id);
            } catch {
              return null;
            }
          })
        )
      ).filter((p): p is ArchitectureProfile => p !== null);

      const currentActive = get().activeProfile;
      let activeToSet = currentActive;
      if (!activeToSet && fullProfiles.length > 0) {
        const activeSummary = summaries.find((s) => s.is_active) || summaries[0];
        activeToSet =
          fullProfiles.find((p) => p.profile_id === activeSummary.profile_id) || fullProfiles[0];
      }

      set({
        architectureProfiles: fullProfiles,
        activeProfile: activeToSet || null,
        isLoadingProfile: false,
      });
    } catch (err) {
      console.error('[wizardStore] fetchArchitectureProfiles error:', err);
      set({ isLoadingProfile: false });
    }
  },

  setActiveProfile: async (profileId: string) => {
    set({ isLoadingProfile: true });
    try {
      await apiClient.selectActiveArchitectureProfile(profileId);
      let profile = get().architectureProfiles.find((p) => p.profile_id === profileId);
      if (!profile) {
        profile = await apiClient.getArchitectureProfile(profileId);
        set((state) => ({
          architectureProfiles: [...state.architectureProfiles, profile!],
        }));
      }
      set({ activeProfile: profile, isLoadingProfile: false });
    } catch (err) {
      console.error('[wizardStore] setActiveProfile error:', err);
      set({ isLoadingProfile: false });
    }
  },

  uploadReferenceMicroservice: async (payload: HarvestReferencePayload) => {
    set({ isLoadingProfile: true });
    try {
      const newProfile = await apiClient.harvestReferenceRepo(payload);
      set((state) => ({
        architectureProfiles: [
          newProfile,
          ...state.architectureProfiles.filter((p) => p.profile_id !== newProfile.profile_id),
        ],
        activeProfile: newProfile,
        isLoadingProfile: false,
      }));
      return newProfile;
    } catch (err) {
      set({ isLoadingProfile: false });
      throw err;
    }
  },

  resetWizard: () => {
    set({
      currentStep: 1,
      maxCompletedStep: 1,
      monolithInfo: null,
      selectedEntrypoint: null,
      selectedEntryPoint: null,
      selectedEntryPoints: new Set<string>(),
      sliceData: null,
      selectedNode: null,
      runId: null,
      activeBatch: null,
      inspectedRunId: null,
      sseConnected: false,
      telemetryLogs: [],
      activePass: 1,
      passStatus: { pass1: 'pending', pass2: 'pending', pass3: 'pending' },
      totalTokens: 0,
      burnRate: 0,
      isExtractionComplete: false,
      specData: null,
      legacySource: '',
      specSha256: '',
      highlightedLines: null,
      activeScenarioName: null,
      hitlApproved: false,
      catalogMatch: null,
      generatedFiles: [],
      selectedFile: null,
    });
  },
}));
