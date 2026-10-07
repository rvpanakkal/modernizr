import React, { useEffect, useRef, useState, useMemo } from 'react';
import { useWizardStore } from '../store/wizardStore';
import { subscribeToRunStream } from '../services/sseClient';
import {
  Terminal,
  ArrowRight,
  Activity,
  CheckCircle2,
  Clock,
  Loader2,
  Copy,
  Check,
  Trash2,
  AlertTriangle,
  Radio,
  Layers,
  Sparkles,
  ShieldAlert,
  Eye,
} from 'lucide-react';

export const TelemetryScreen: React.FC = () => {
  const {
    runId,
    activeBatch,
    inspectedRunId,
    selectedEntryPoint,
    activeProfile,
    currentPass,
    passStates,
    terminalLogs,
    isExtracting,
    isExtractionComplete,
    totalTokens,
    burnRate,
    sseConnected,
    currentSpec,
    startExtraction,
    setInspectedRunId,
    clearTerminalLogs,
    setStep,
    proceedToHitlReview,
    appendTerminalToken,
    updatePassState,
    handleExtractionComplete,
    handleExtractionError,
    setSseConnected,
  } = useWizardStore();

  const effectiveRunId = inspectedRunId || runId;
  const sseSubRef = useRef<{ close: () => void } | null>(null);

  const terminalContainerRef = useRef<HTMLDivElement>(null);
  const [userHasScrolledUp, setUserHasScrolledUp] = useState<boolean>(false);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [isCopied, setIsCopied] = useState<boolean>(false);

  // Auto-initiate extraction if not already running or completed and not in batch mode
  useEffect(() => {
    if (!runId && !isExtracting && !isExtractionComplete && !activeBatch) {
      startExtraction();
    }
  }, [runId, isExtracting, isExtractionComplete, activeBatch, startExtraction]);

  // Fix 1: Clean SSE Subscription Management (Strictly dependent on effectiveRunId primitive)
  useEffect(() => {
    if (!effectiveRunId) return;

    // Guard: if already completed and currentSpec matches this runId, avoid redundant connection
    if (isExtractionComplete && currentSpec?.run_id === effectiveRunId) {
      return;
    }

    // Clean up any existing connection before opening a new one
    if (sseSubRef.current) {
      sseSubRef.current.close();
      sseSubRef.current = null;
    }

    setSseConnected(true);

    const sse = subscribeToRunStream(effectiveRunId, {
      onToken: (token) => appendTerminalToken(token),
      onPassStarted: (pass) => updatePassState(pass, 'RUNNING'),
      onPassCompleted: (pass, stats) => updatePassState(pass, 'COMPLETED', stats),
      onComplete: (spec) => {
        // CRITICAL: Close the connection so browser EventSource does not retry infinitely
        sse.close();
        setSseConnected(false);
        handleExtractionComplete(spec);
      },
      onError: (err) => {
        sse.close();
        setSseConnected(false);
        handleExtractionError(err);
      },
    });

    sseSubRef.current = sse;

    return () => {
      if (sseSubRef.current) {
        sseSubRef.current.close();
        sseSubRef.current = null;
      }
      setSseConnected(false);
    };
  }, [effectiveRunId]); // ONLY effectiveRunId in dependency array

  // Fix 2: Container-Scoped Terminal Auto-Scroll (No window or parent jumps)
  const handleScroll = () => {
    if (!terminalContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = terminalContainerRef.current;
    // If user is within 60px of the bottom, keep auto-scrolling active
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 60;
    setUserHasScrolledUp(!isNearBottom);
  };

  useEffect(() => {
    if (autoScroll && !userHasScrolledUp && terminalContainerRef.current) {
      terminalContainerRef.current.scrollTop = terminalContainerRef.current.scrollHeight;
    }
  }, [terminalLogs, autoScroll, userHasScrolledUp]);

  const handleCopyLogs = () => {
    const text = terminalLogs.join('');
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const maxTokens = 6000;
  const tokenPercentage = Math.min(Math.round((totalTokens / maxTokens) * 100), 100);

  const getTokenBarColor = () => {
    if (totalTokens < 4000) return 'bg-emerald-500';
    if (totalTokens <= 5500) return 'bg-amber-500';
    return 'bg-rose-500';
  };

  const getTokenTextColor = () => {
    if (totalTokens < 4000) return 'text-emerald-400';
    if (totalTokens <= 5500) return 'text-amber-400';
    return 'text-rose-400';
  };

  const inspectedSlice = activeBatch?.slices.find((s) => s.run_id === inspectedRunId);

  const activeTargetName =
    inspectedSlice?.class_name ||
    selectedEntryPoint?.class_name ||
    selectedEntryPoint?.simple_name ||
    selectedEntryPoint?.fqn?.split('.').pop() ||
    'TransferManagedBean';

  const profileBadgeName =
    activeProfile?.name ||
    'Enterprise Spring Boot 3.5 Standard';

  // Compute active pass latency in ms
  const activePassLatency = useMemo(() => {
    if (currentPass && passStates[currentPass]) {
      return passStates[currentPass].latencyMs;
    }
    return 0;
  }, [currentPass, passStates]);

  const isBatchComplete =
    activeBatch &&
    (activeBatch.status === 'COMPLETED' || activeBatch.status === 'PARTIAL_FAILURE');

  const isComplete = activeBatch
    ? Boolean(isBatchComplete)
    : Boolean(isExtractionComplete || currentSpec);

  const canProceed = !isExtracting && isComplete && (activeBatch ? true : Boolean(currentSpec));

  const passes = [
    {
      num: 1 as const,
      name: 'Technical Decompiler',
      role: 'Pass 1',
      state: passStates[1],
      desc: 'Strip container plumbing, JSF context, @ManagedBean, and transaction boilerplates.',
      fallbackOutput: '5 core operations isolated; container plumbing stripped.',
    },
    {
      num: 2 as const,
      name: 'Business Abstractor',
      role: 'Pass 2',
      state: passStates[2],
      desc: 'Extract technology-agnostic business invariants, calculation thresholds, and policies.',
      fallbackOutput: '5 domain invariants extracted with line-level traceability.',
    },
    {
      num: 3 as const,
      name: 'Spec Formatter',
      role: 'Pass 3',
      state: passStates[3],
      desc: 'Synthesize Gherkin BDD scenarios, OpenAPI 3.0 contracts, and bidirectional line mappings.',
      fallbackOutput: '4 Gherkin BDD scenarios and OpenAPI 3.0 YAML synthesized.',
    },
  ];

  return (
    <div className="flex flex-col gap-4 flex-1 h-full w-full max-w-7xl mx-auto overflow-hidden">
      {/* 1. TOP HEADER & RUN HUD */}
      <div className="shrink-0 flex flex-col lg:flex-row lg:items-center justify-between gap-3 p-3.5 bg-slate-900 border border-slate-800 rounded-xl shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 font-mono text-xs">
            <span className="font-bold text-sky-400 bg-sky-950/80 px-2 py-0.5 rounded border border-sky-800/60">
              STEP 03
            </span>
            <span className="text-slate-300 font-bold tracking-tight text-sm">
              Cognitive Extraction Telemetry
            </span>
          </div>

          <div className="h-4 w-px bg-slate-700 hidden sm:block" />

          {/* Run ID HUD */}
          <div className="flex items-center gap-1.5 text-xs font-mono text-slate-300 bg-slate-950 px-2.5 py-1 rounded-md border border-slate-800">
            <span className="text-slate-500">Run:</span>
            <strong className="text-sky-300">#{effectiveRunId || 'run-init'}</strong>
          </div>

          {/* Batch Status HUD */}
          {activeBatch && (
            <div className="flex items-center gap-1.5 text-xs font-mono text-slate-300 bg-slate-950 px-2.5 py-1 rounded-md border border-slate-800">
              <span className="text-slate-500">Batch:</span>
              <strong className="text-sky-300">
                {activeBatch.completed_slices}/{activeBatch.total_slices} Done
              </strong>
            </div>
          )}

          {/* Target HUD */}
          <div className="flex items-center gap-1.5 text-xs font-mono text-slate-300 bg-slate-950 px-2.5 py-1 rounded-md border border-slate-800">
            <span className="text-slate-500">Target:</span>
            <strong className="text-emerald-300 truncate max-w-[200px]" title={activeTargetName}>
              {activeTargetName}
            </strong>
          </div>

          {/* Architecture Profile Badge */}
          <div className="hidden md:flex items-center gap-1.5 text-xs font-mono text-slate-300 bg-slate-950 px-2.5 py-1 rounded-md border border-slate-800">
            <Layers className="h-3.5 w-3.5 text-indigo-400" />
            <span className="text-indigo-300 truncate max-w-[220px]" title={profileBadgeName}>
              {profileBadgeName}
            </span>
          </div>
        </div>

        {/* Live Streaming Indicator */}
        <div className="flex items-center gap-3">
          {isExtractionComplete ? (
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-950/80 border border-emerald-800/80 rounded-full text-emerald-400 text-xs font-mono font-bold shadow-sm">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>{activeBatch ? 'BATCH EXTRACTION SEALED' : 'EXTRACTION SEALED'}</span>
            </div>
          ) : isExtracting || sseConnected ? (
            <div className="flex items-center gap-2 px-3 py-1 bg-sky-950/80 border border-sky-800/80 rounded-full text-sky-400 text-xs font-mono font-bold shadow-sm animate-pulse">
              <Radio className="h-3.5 w-3.5 text-sky-400 animate-spin" />
              <span>LIVE REASONING STREAM ACTIVE</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1 bg-slate-800/80 border border-slate-700/80 rounded-full text-slate-400 text-xs font-mono">
              <Radio className="h-3.5 w-3.5 text-slate-500" />
              <span>STREAM IDLE</span>
            </div>
          )}

          {/* Token Burn Rate */}
          {burnRate > 0 && isExtracting && (
            <div className="hidden sm:flex items-center gap-1 px-2.5 py-1 rounded bg-slate-950 border border-slate-800 text-xs font-mono text-amber-400">
              <Activity className="h-3.5 w-3.5" />
              <span>~{burnRate} tok/s</span>
            </div>
          )}
        </div>
      </div>

      {/* 1.1 BATCH SLICES CAROUSEL / SELECTOR (Shown in Batch Mode) */}
      {activeBatch && activeBatch.slices.length > 0 && (
        <div className="shrink-0 p-3 bg-slate-900 border border-slate-800 rounded-xl flex flex-col gap-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="font-bold text-slate-300 flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5 text-sky-400" />
              BATCH RUN SLICES ({activeBatch.slices.length}) — Click to Inspect Live Stream:
            </span>
            <span className="text-slate-400">
              Worker Pool: 3 concurrent | Overall Progress:{' '}
              {Math.round((activeBatch.completed_slices / activeBatch.total_slices) * 100)}%
            </span>
          </div>

          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
            {activeBatch.slices.map((slice) => {
              const isSelected = slice.run_id === inspectedRunId;
              const isSliceDone = slice.status === 'COMPLETED';
              const isSliceRunning = slice.status === 'RUNNING';

              return (
                <button
                  key={slice.run_id}
                  onClick={() => setInspectedRunId(slice.run_id)}
                  className={`px-3 py-2 rounded-lg border text-left flex flex-col gap-1 transition-all shrink-0 min-w-[200px] cursor-pointer ${
                    isSelected
                      ? 'bg-sky-950/60 border-sky-500 ring-1 ring-sky-500 shadow-md'
                      : 'bg-slate-950/80 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-bold text-white truncate max-w-[130px]">
                      {slice.class_name}
                    </span>
                    {isSliceDone && <CheckCircle2 className="h-3 w-3 text-emerald-400 shrink-0" />}
                    {isSliceRunning && <Loader2 className="h-3 w-3 text-sky-400 animate-spin shrink-0" />}
                  </div>

                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span
                      className={`font-semibold ${
                        isSliceDone
                          ? 'text-emerald-400'
                          : isSliceRunning
                          ? 'text-sky-300'
                          : 'text-slate-400'
                      }`}
                    >
                      {slice.status === 'RUNNING' ? `Pass ${slice.current_pass || 1}` : slice.status}
                    </span>

                    <span className="text-slate-400 text-[10px]">
                      {slice.tokens_consumed > 0 ? `${slice.tokens_consumed.toLocaleString()} tok` : '--'}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 2. 3-CARD VISUAL STEPPER */}
      <div className="shrink-0 grid grid-cols-1 md:grid-cols-3 gap-3.5">
        {passes.map((p) => {
          const isRunning = p.state?.status === 'RUNNING';
          const isCompleted = p.state?.status === 'COMPLETED';
          const isPending = !isRunning && !isCompleted;

          const latencySec = (p.state?.latencyMs ? p.state.latencyMs / 1000 : 0).toFixed(1);
          const tokensFormatted = p.state?.tokens ? p.state.tokens.toLocaleString() : '0';

          return (
            <div
              key={p.num}
              className={`p-4 rounded-xl border flex flex-col justify-between transition-all duration-300 ${
                isRunning
                  ? 'bg-sky-950/40 border-sky-500 ring-1 ring-sky-500/50 shadow-lg shadow-sky-500/10'
                  : isCompleted
                  ? 'bg-slate-900 border-slate-800/80 hover:border-slate-700'
                  : 'bg-slate-950/60 border-slate-900 opacity-60'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono font-bold text-sky-400 uppercase tracking-wider">
                    {p.role}
                  </span>

                  {/* Status Badge */}
                  <div className="flex items-center gap-1.5 text-[11px] font-mono font-semibold">
                    {isRunning && (
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-sky-950 border border-sky-700 text-sky-300 animate-pulse">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Running...
                      </span>
                    )}
                    {isCompleted && (
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950 border border-emerald-800 text-emerald-300">
                        <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                        Completed
                      </span>
                    )}
                    {isPending && (
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-900 border border-slate-800 text-slate-500">
                        <Clock className="h-3 w-3" />
                        Pending
                      </span>
                    )}
                  </div>
                </div>

                <h3 className="text-sm font-bold text-white mb-1 tracking-tight">
                  {p.name}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed mb-3">
                  {p.desc}
                </p>
              </div>

              {/* Bottom Metrics Pill */}
              <div className="pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono">
                <span className="text-slate-500">Tally:</span>
                {isCompleted ? (
                  <span className="text-sky-300 font-semibold">
                    ✔ Completed ({latencySec}s, {tokensFormatted} tok)
                  </span>
                ) : isRunning ? (
                  <span className="text-amber-300 font-semibold animate-pulse">
                    ◉ Streaming ({latencySec}s, {tokensFormatted} tok)
                  </span>
                ) : (
                  <span className="text-slate-500">○ Pending</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 3. LIVE TERMINAL VIEWER (Strict Layout Bounds: flex-1 min-h-0) */}
      <div className="flex-1 min-h-0 flex flex-col bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
        {/* Terminal HUD & Controls */}
        <div className="shrink-0 flex items-center justify-between px-4 py-2.5 bg-slate-900/90 border-b border-slate-800 text-xs font-mono">
          <div className="flex items-center gap-2 text-slate-200">
            <Terminal className="h-4 w-4 text-sky-400" />
            <span className="font-bold">LIVE REASONING & TOKEN STREAM</span>
            <span className="text-[10px] text-slate-500">
              ({terminalLogs.length} chunks)
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyLogs}
              title="Copy Output"
              className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition text-[11px]"
            >
              {isCopied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
              <span>{isCopied ? 'Copied!' : 'Copy Output'}</span>
            </button>

            <button
              onClick={clearTerminalLogs}
              title="Clear Console"
              className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition text-[11px]"
            >
              <Trash2 className="h-3 w-3" />
              <span>Clear</span>
            </button>

            <label className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800/60 border border-slate-700/60 text-[11px] text-slate-300 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => {
                  const checked = e.target.checked;
                  setAutoScroll(checked);
                  if (checked) {
                    setUserHasScrolledUp(false);
                    if (terminalContainerRef.current) {
                      terminalContainerRef.current.scrollTop = terminalContainerRef.current.scrollHeight;
                    }
                  }
                }}
                className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0"
              />
              Auto-Scroll
            </label>
          </div>
        </div>

        {/* Monospace Code Stream — Container-Bounded Scrolling */}
        <div
          ref={terminalContainerRef}
          onScroll={handleScroll}
          className="flex-1 min-h-0 p-4 font-mono text-xs overflow-y-auto space-y-1 bg-slate-950/95 leading-relaxed text-slate-300"
        >
          {terminalLogs.length === 0 ? (
            <div className="text-slate-600 italic py-6 text-center">
              Waiting for cognitive extraction telemetry stream...
            </div>
          ) : (
            terminalLogs.map((chunk, idx) => {
              const isHeader = chunk.startsWith('[Pass');
              return (
                <div
                  key={idx}
                  className={`whitespace-pre-wrap break-all ${
                    isHeader ? 'text-sky-300 font-bold' : 'text-slate-300'
                  }`}
                >
                  {chunk}
                </div>
              );
            })
          )}

          {/* Smooth Pulsing Cursor */}
          {isExtracting && (
            <span className="inline-block text-sky-400 font-bold text-sm animate-pulse ml-0.5 select-none">
              █
            </span>
          )}
        </div>
      </div>

      {/* 4. METRICS & STEP HANDOFF FOOTER */}
      <div className="shrink-0 p-4 bg-slate-900 border border-slate-800 rounded-xl shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Token Budget Gauge */}
        <div className="flex-1 flex flex-col gap-1.5 max-w-md">
          <div className="flex items-center justify-between font-mono text-xs">
            <span className="text-slate-400 flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5 text-sky-400" />
              {activeBatch ? 'Inspected Slice Tokens:' : 'Cumulative Generation Tokens:'}
            </span>
            <span className={`font-bold ${getTokenTextColor()}`}>
              {totalTokens.toLocaleString()} / {maxTokens.toLocaleString()} budget
            </span>
          </div>

          <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
            <div
              className={`h-2 rounded-full transition-all duration-300 ${getTokenBarColor()}`}
              style={{ width: `${tokenPercentage}%` }}
            />
          </div>

          <div className="flex items-center justify-between font-mono text-[10px] text-slate-500">
            <span>{tokenPercentage}% of 6k budget</span>
            {activeBatch ? (
              <span className="text-slate-400 font-semibold">
                Batch: {activeBatch.completed_slices}/{activeBatch.total_slices} Completed
              </span>
            ) : (
              <span>Active Pass Latency: {activePassLatency.toLocaleString()} ms</span>
            )}
          </div>
        </div>

        {/* Manual Action & Step Handoff Controls */}
        <div className="flex items-center gap-3">
          {canProceed ? (
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-950/80 border border-emerald-800/80 text-emerald-300 text-xs font-mono">
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                <span>
                  ✔ Extraction Complete — Ready for Review
                  {activeBatch ? ` (${activeBatch.completed_slices}/${activeBatch.total_slices} Slices)` : ''}
                </span>
              </div>

              <button
                onClick={proceedToHitlReview}
                disabled={isExtracting || (!currentSpec && !activeBatch)}
                className="px-5 py-2.5 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 disabled:text-slate-600 text-white font-medium text-xs rounded transition flex items-center gap-2 shadow-lg cursor-pointer disabled:cursor-not-allowed"
              >
                Proceed to HITL Review <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 text-xs font-mono text-slate-400 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-400" />
                <span>
                  {activeBatch
                    ? `Batch Running: ${activeBatch.completed_slices} / ${activeBatch.total_slices} slices completed (3-worker pool)...`
                    : 'Extraction In Progress...'}
                </span>
              </div>

              <button
                onClick={proceedToHitlReview}
                disabled={true}
                className="px-5 py-2.5 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 disabled:text-slate-600 text-white font-medium text-xs rounded transition flex items-center gap-2 shadow-lg cursor-not-allowed"
              >
                Proceed to HITL Review <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
