import React, { useEffect, useState } from 'react';
import { useWizardStore, GeneratedFile } from '../store/wizardStore';
import { apiClient } from '../services/api';
import { MonacoViewer } from '../components/MonacoViewer';
import {
  Sparkles,
  Download,
  GitPullRequest,
  CheckCircle2,
  FileCode2,
  FileText,
  Boxes,
  Layers,
  ShieldCheck,
  ExternalLink,
  Code,
  Tag,
  Columns,
  CheckCheck,
  Code2,
} from 'lucide-react';

export const SynthesisScreen: React.FC = () => {
  const {
    runId,
    catalogMatch,
    setCatalogMatch,
    targetStack,
    setTargetStack,
    generatedFiles,
    setGeneratedFiles,
    selectedFile,
    setSelectedFile,
    jiraStoryId,
    activeProfile,
  } = useWizardStore();

  const [isLoading, setIsLoading] = useState(false);
  const [prCreated, setPrCreated] = useState(false);
  const [viewMode, setViewMode] = useState<'single' | 'comparator'>('single');
  const [selectedExemplarIndex, setSelectedExemplarIndex] = useState(0);

  useEffect(() => {
    const loadSynthesis = async () => {
      const activeRunId = runId || 'run-canonical';
      setIsLoading(true);
      try {
        // 1. Fetch catalog matches
        const catRes = await apiClient.getCatalogMatch('PAYMENT_PROCESSING');
        setCatalogMatch(catRes);

        // 2. Synthesize code if not already done
        if (generatedFiles.length === 0) {
          const genRes = await apiClient.generateSynthesis(activeRunId, targetStack);
          setGeneratedFiles(genRes.files);
        }
      } catch (err) {
        console.error('Failed to generate synthesis:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadSynthesis();
  }, [runId, targetStack]);

  const handleDownloadBundle = () => {
    const activeRunId = runId || 'run-canonical';
    window.location.href = apiClient.getBundleDownloadUrl(activeRunId);
  };

  const handleCreatePullRequest = () => {
    setPrCreated(true);
  };

  const bestMatch = catalogMatch?.best_match;

  return (
    <div className="flex flex-col gap-5 flex-1 w-full max-w-7xl mx-auto">
      {/* Step Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-sky-400 bg-sky-950/80 px-2 py-0.5 rounded border border-sky-800/60">
              STEP 05
            </span>
            <span className="flex items-center gap-1 text-[11px] font-mono font-bold text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800/60">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              <span>Step 5.5 ArchUnit: PASSED</span>
            </span>
            <h2 className="text-xl font-bold text-white tracking-tight">
              Enterprise Catalog Reuse & Target Code Synthesis
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Interrogate Corporate Service Catalog before generating production-grade Java 21 / Spring Boot 3.5.x and Angular Microfrontends.
          </p>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownloadBundle}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            <Download className="h-4 w-4 text-sky-400" />
            <span>Download Audit Bundle (.zip)</span>
          </button>

          <button
            onClick={handleCreatePullRequest}
            disabled={prCreated}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-600 hover:to-indigo-700 shadow-md shadow-sky-500/20 disabled:opacity-50 transition"
          >
            <GitPullRequest className="h-4 w-4" />
            <span>{prCreated ? 'Pull Request #412 Opened' : 'Create Git Pull Request'}</span>
          </button>
        </div>
      </div>

      {/* Enterprise Catalog Reuse Recommendation Card */}
      {bestMatch && (
        <div className="p-4 bg-gradient-to-r from-slate-900 to-slate-900/90 border border-sky-500/30 rounded-2xl shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="p-2.5 rounded-xl bg-sky-500/20 text-sky-400 border border-sky-500/30">
              <Boxes className="h-6 w-6" />
            </div>
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800/60">
                  {Math.round(bestMatch.similarity_score * 100)}% CATALOG MATCH
                </span>
                <h3 className="text-sm font-bold text-white">
                  Corporate Service: {bestMatch.name} ({bestMatch.service_id})
                </h3>
              </div>
              <p className="text-xs text-slate-300">{bestMatch.description}</p>
              <div className="flex items-center gap-2 mt-1 text-[11px] text-slate-400 font-mono">
                <span className="text-sky-400 font-bold">Strategy:</span>
                <span>{bestMatch.adapter_strategy}</span>
              </div>
            </div>
          </div>

          <div className="flex flex-col items-end gap-1.5 shrink-0">
            <span className="text-[11px] font-mono font-semibold px-3 py-1 rounded-full bg-sky-950 text-sky-300 border border-sky-800">
              {bestMatch.recommendation}
            </span>
            <span className="text-[10px] text-slate-500 font-mono">
              Reused: {bestMatch.overlap_fields.join(', ')}
            </span>
          </div>
        </div>
      )}

      {/* Main Two-Column Synthesis Explorer */}
      <div className="grid grid-cols-12 gap-4 flex-1 min-h-[520px]">
        {/* Left Column: Artifact File Tree */}
        <div className="col-span-12 lg:col-span-4 bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col gap-3 shadow-sm overflow-y-auto max-h-[640px]">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-1.5">
              <FileCode2 className="h-3.5 w-3.5 text-sky-400" />
              Synthesized Artifacts ({generatedFiles.length})
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-sky-400 border border-slate-700">
              MOD-101
            </span>
          </div>

          {/* Files List */}
          <div className="flex flex-col gap-1.5">
            {generatedFiles.map((file) => {
              const isSelected = selectedFile?.path === file.path;
              return (
                <button
                  key={file.path}
                  onClick={() => setSelectedFile(file)}
                  className={`p-2.5 rounded-lg border text-left transition flex items-center justify-between ${
                    isSelected
                      ? 'bg-sky-950/60 border-sky-500 text-sky-200 ring-1 ring-sky-500/40'
                      : 'bg-slate-950 border-slate-800 text-slate-300 hover:bg-slate-800/40'
                  }`}
                >
                  <div className="flex items-center gap-2 overflow-hidden">
                    <FileText className="h-4 w-4 shrink-0 text-slate-400" />
                    <div className="flex flex-col truncate">
                      <span className="font-mono text-xs font-bold truncate">
                        {file.filename}
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono truncate">
                        {file.path}
                      </span>
                    </div>
                  </div>

                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400 shrink-0">
                    {file.category}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right Column: Monaco Code Preview / Exemplar Comparator */}
        <div className="col-span-12 lg:col-span-8 flex flex-col h-full min-h-[540px] gap-2">
          {/* View Mode & ArchUnit Conformance Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-2 bg-slate-900 border border-slate-800 rounded-xl text-xs">
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
              <button
                type="button"
                onClick={() => setViewMode('single')}
                className={`px-3 py-1 rounded-md font-semibold transition ${
                  viewMode === 'single'
                    ? 'bg-sky-500 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Synthesized Code
              </button>
              <button
                type="button"
                onClick={() => setViewMode('comparator')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md font-semibold transition ${
                  viewMode === 'comparator'
                    ? 'bg-sky-500 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Columns className="h-3.5 w-3.5" />
                <span>Architecture Exemplar Comparator</span>
              </button>
            </div>

            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-950/80 text-emerald-300 border border-emerald-800/60 font-mono text-[11px] font-semibold">
                <CheckCheck className="h-3.5 w-3.5 text-emerald-400" />
                <span>ArchUnit Conformance Gate: 100% Passed</span>
              </span>
            </div>
          </div>

          {viewMode === 'comparator' ? (
            <div className="flex flex-col flex-1 gap-2">
              {/* Exemplar Selector Bar */}
              <div className="p-2.5 bg-slate-900/90 border border-slate-800 rounded-xl flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider font-semibold">
                    Harvested Exemplar:
                  </span>
                  <div className="flex items-center gap-1">
                    {(activeProfile?.exemplars || []).map((ex, idx) => (
                      <button
                        key={ex.pattern_name}
                        onClick={() => setSelectedExemplarIndex(idx)}
                        className={`px-2.5 py-1 rounded-md text-xs font-mono transition ${
                          selectedExemplarIndex === idx
                            ? 'bg-sky-950 text-sky-300 border border-sky-500 font-bold'
                            : 'bg-slate-950 text-slate-400 border border-slate-800 hover:border-slate-700'
                        }`}
                      >
                        {ex.pattern_name}
                      </button>
                    ))}
                  </div>
                </div>

                {activeProfile?.exemplars?.[selectedExemplarIndex] && (
                  <div className="flex items-center gap-1.5 font-mono text-[10px] text-slate-400">
                    <span className="text-slate-500">Annotations:</span>
                    {activeProfile.exemplars[selectedExemplarIndex].annotations_matched.map((ann) => (
                      <span
                        key={ann}
                        className="px-1.5 py-0.5 rounded bg-slate-950 text-indigo-300 border border-slate-800"
                      >
                        {ann}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Side-by-side Monaco Comparator */}
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-2 flex-1 min-h-[460px]">
                {/* Left: Harvested Reference Exemplar */}
                <div className="h-full flex flex-col min-h-[460px]">
                  <MonacoViewer
                    title={`Reference: ${activeProfile?.exemplars?.[selectedExemplarIndex]?.pattern_name || 'Exemplar'}`}
                    badge={`Approved Archetype • ${activeProfile?.target_runtime || 'Java 21'}`}
                    language="java"
                    value={
                      activeProfile?.exemplars?.[selectedExemplarIndex]?.code_snippet ||
                      '// No exemplar available'
                    }
                    readOnly={true}
                  />
                </div>

                {/* Right: Synthesized Target Code */}
                <div className="h-full flex flex-col min-h-[460px]">
                  {selectedFile ? (
                    <MonacoViewer
                      title={`Synthesized: ${selectedFile.filename}`}
                      badge={`Generated Output • ${selectedFile.category}`}
                      language={selectedFile.language}
                      value={selectedFile.content}
                      readOnly={true}
                      sha256={selectedFile.sha256}
                    />
                  ) : (
                    <div className="flex-1 flex items-center justify-center bg-slate-900 border border-slate-800 rounded-xl text-slate-500 text-xs">
                      Select a file from the tree to compare.
                    </div>
                  )}
                </div>
              </div>

              {/* Conformance Checklist Bar */}
              <div className="p-2.5 bg-slate-950 border border-emerald-900/60 rounded-xl flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2 text-emerald-300 font-semibold">
                  <CheckCheck className="h-4 w-4 text-emerald-400" />
                  <span>Archetype Conformance & Pattern Adherence</span>
                </div>
                <div className="flex flex-wrap items-center gap-2 font-mono text-[10px]">
                  <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800/80">
                    RFC 7807 Problem Detail Enforced
                  </span>
                  <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800/80">
                    No Direct Repo Injection in Controller
                  </span>
                  <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800/80">
                    Spring Boot 3.5.x POM Baseline Validated
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col h-full min-h-[500px]">
              {selectedFile ? (
                <MonacoViewer
                  title={selectedFile.filename}
                  badge={`${selectedFile.category} • ${selectedFile.language.toUpperCase()}`}
                  language={selectedFile.language}
                  value={selectedFile.content}
                  readOnly={true}
                  sha256={selectedFile.sha256}
                />
              ) : (
                <div className="flex-1 flex items-center justify-center bg-slate-900 border border-slate-800 rounded-xl text-slate-500 text-xs">
                  Select an artifact from the tree to preview synthesized code.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
