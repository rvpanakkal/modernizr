import { create } from 'zustand';
import {
  ArchitectureProfile,
  HarvestReferencePayload,
  ProfileSummary,
} from '../types/architecture';
import { apiClient } from '../services/api';

export interface EntrypointItem {
  fqn: string;
  simple_name: string;
  layer: string;
  role: string;
  kind: string;
  annotations: string[];
  injected_dependencies: string[];
  description: string;
}

export interface GraphNode {
  id: string;
  name: string;
  fqn: string;
  role: string;
  layer: string;
  color: string;
  annotations: string[];
  methods: string[];
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  label: string;
}

export interface SliceData {
  slice_id: string;
  entry_fqn: string;
  max_depth: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  execution_paths: string[];
  component_summary: Array<{ fqn: string; role: string; layer: string }>;
  estimated_tokens: number;
  max_tokens: number;
  within_budget: boolean;
  legacy_source: string;
  raw_slice: any;
}

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

interface WizardState {
  currentStep: number;
  maxCompletedStep: number;

  // Screen 1: Source Ingest
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
  entrypoints: EntrypointItem[];
  selectedEntrypoint: EntrypointItem | null;
  sliceDepth: number;
  sliceData: SliceData | null;
  selectedNode: GraphNode | null;

  // Screen 3: Telemetry
  runId: string | null;
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

  // Screen 4: HITL Review
  specData: GeneratedSpec | null;
  legacySource: string;
  specSha256: string;
  highlightedLines: [number, number] | null;
  activeScenarioName: string | null;
  hitlApproved: boolean;
  approvedBy: string;
  jiraStoryId: string;

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
  setStep: (step: number) => void;
  setMonolithInfo: (info: any) => void;
  setEntrypoints: (entries: EntrypointItem[]) => void;
  selectEntrypoint: (entry: EntrypointItem) => void;
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

  monolithInfo: null,

  // Architecture Profile State
  architectureProfiles: [],
  activeProfile: null,
  isLoadingProfile: false,

  entrypoints: [],
  selectedEntrypoint: null,
  sliceDepth: 5,
  sliceData: null,
  selectedNode: null,

  runId: null,
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

  specData: null,
  legacySource: '',
  specSha256: '',
  highlightedLines: null,
  activeScenarioName: null,
  hitlApproved: false,
  approvedBy: '',
  jiraStoryId: 'MOD-101',

  catalogMatch: null,
  targetStack: 'spring_boot_3_5',
  generatedFiles: [],
  selectedFile: null,

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

  setEntrypoints: (entries: EntrypointItem[]) => {
    set({ entrypoints: entries });
    if (entries.length > 0 && !get().selectedEntrypoint) {
      set({ selectedEntrypoint: entries[0] });
    }
  },

  selectEntrypoint: (entry: EntrypointItem) => {
    set({ selectedEntrypoint: entry });
  },

  setSliceDepth: (depth: number) => {
    set({ sliceDepth: depth });
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
      sliceData: null,
      selectedNode: null,
      runId: null,
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
