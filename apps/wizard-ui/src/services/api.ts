import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const apiClient = {
  // Screen 1: Source Ingestion
  async uploadSource(formData: FormData) {
    const res = await api.post('/api/source/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  // Screen 2: Graph & Topology
  async getEntrypoints() {
    const res = await api.get('/api/graph/entrypoints');
    return res.data;
  },

  async getVerticalSlice(entryFqn: string, maxDepth: number = 5) {
    const res = await api.post('/api/graph/slice', {
      entry_fqn: entryFqn,
      max_depth: maxDepth,
    });
    return res.data;
  },

  // Screen 3: Pipeline Runs & Telemetry
  async startPipelineRun(entryFqn: string, sliceData?: any, trackerType: string = 'jira') {
    const res = await api.post('/api/pipeline/runs', {
      entry_fqn: entryFqn,
      slice_data: sliceData,
      tracker_type: trackerType,
    });
    return res.data;
  },

  // Screen 4: HITL Review & Jira Gate
  async getSpec(runId: string) {
    const res = await api.get(`/api/spec/${runId}`);
    return res.data;
  },

  async approveHitl(runId: string, approvedBy: string, comments?: string, specSha256?: string) {
    const res = await api.post('/api/hitl/approve', {
      run_id: runId,
      approved_by: approvedBy,
      comments,
      spec_sha256: specSha256,
    });
    return res.data;
  },

  async reviseHitl(runId: string, feedback: string, targetPass: number = 2) {
    const res = await api.post('/api/hitl/revise', {
      run_id: runId,
      feedback,
      target_pass: targetPass,
    });
    return res.data;
  },

  // Screen 5: Catalog & Synthesis
  async getCatalogMatch(domain: string = 'PAYMENT_PROCESSING') {
    const res = await api.get(`/api/catalog/match?domain=${encodeURIComponent(domain)}`);
    return res.data;
  },

  async generateSynthesis(runId: string, targetStack: string = 'spring_boot_3_5') {
    const res = await api.post('/api/synthesis/generate', {
      run_id: runId,
      target_stack: targetStack,
      generate_ui: true,
      generate_openapi: true,
    });
    return res.data;
  },

  getBundleDownloadUrl(runId: string): string {
    return `/api/synthesis/bundle/${runId}`;
  },
};
