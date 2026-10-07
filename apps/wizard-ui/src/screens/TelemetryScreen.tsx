import React, { useEffect, useRef, useState, useMemo } from 'react';
import { useWizardStore } from '../store/wizardStore';
import { sseClient } from '../services/sseClient';
import {
  Terminal,
  ArrowRight,
  Activity,
  CheckCircle2,
  Clock,
  Loader2,
  Pause,
  Play,
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
  } = useWizardStore();

  const terminalEndRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [isCopied, setIsCopied] = useState<boolean>(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [isAutoAdvancePaused, setIsAutoAdvancePaused] = useState<boolean>(false);
  const countdownTimerRef = useRef<any>(null);

  // Auto-initiate extraction if not already running or completed and not in batch mode
  useEffect(() => {
    if (!runId && !isExtracting && !isExtractionComplete && !activeBatch) {
      startExtraction();
    }
  }, [runId, isExtracting, isExtractionComplete, activeBatch, startExtraction]);

  // Terminal auto-scrolling
  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [terminalLogs, autoScroll]);

  // Handle 2-second countdown auto-advance on extraction complete
  useEffect(() => {
    if (isExtractionComplete && countdown === null && !isAutoAdvancePaused) {
      setCountdown(2);
    }
  }, [isExtractionComplete, countdown, isAutoAdvancePaused]);

  useEffect(() => {
    if (countdown === null || isAutoAdvancePaused) return;

    if (countdown === 0) {
      setStep(4);
      return;
    }

    countdownTimerRef.current = setTimeout(() => {
      setCountdown((prev) => (prev !== null && prev > 0 ? prev - 1 : 0));
    }, 1000);

    return () => {
      if (countdownTimerRef.current) {
        clearTimeout(countdownTimerRef.current);
      }
    };
  }, [countdown, isAutoAdvancePaused, setStep]);

  const handleCopyLogs = () => {
    const text = terminalLogs.join('');
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleToggleAutoAdvance = () => {
    setIsAutoAdvancePaused((prev) => !prev);
  };

  const handleProceedImmediately = () => {
    if (countdownTimerRef.current) {
      clearTimeout(countdownTimerRef.current);
    }
    setStep(4);
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
    <div className="flex flex-col gap-4 flex-1 h-full w-full max-w-7xl mx-auto">
      {/* 1. TOP HEADER & RUN HUD */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 p-3.5 bg-slate-900 border border-slate-800 rounded-xl shadow-sm">
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
            <strong className="text-sky-300">#{inspectedRunId || runId || 'run-init'}</strong>
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
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              <span>{activeBatch ? 'LIVE BATCH SSE STREAM' : 'LIVE SSE STREAM'}</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1 bg-slate-950 border border-slate-800 rounded-full text-slate-500 text-xs font-mono">
              <Radio className="h-3 w-3" />
              <span>CONNECTING...</span>
            </div>
          )}
        </div>
      </div>

      {/* 1.5 BATCH QUEUE MATRIX & ACTIVE STREAM SWITCHER */}
      {activeBatch && activeBatch.slices.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2 text-xs font-mono">
              <Layers className="h-4 w-4 text-sky-400" />
              <span className="font-bold text-slate-200">BATCH QUEUE MATRIX</span>
              <span className="text-slate-500 text-[11px]">
                ({activeBatch.completed_slices} of {activeBatch.total_slices} slices complete)
              </span>
            </div>
            <div className="flex items-center gap-2 text-[11px] font-mono">
              <span className="text-slate-400">Batch ID:</span>
              <span className="text-sky-300 font-bold">#{activeBatch.batch_id.slice(0, 10)}</span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                  activeBatch.status === 'COMPLETED'
                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    : activeBatch.status === 'PARTIAL_FAILURE'
                    ? 'bg-amber-950 text-amber-400 border border-amber-800'
                    : activeBatch.status === 'FAILED'
                    ? 'bg-rose-950 text-rose-400 border border-rose-800'
                    : 'bg-sky-950 text-sky-400 border border-sky-800 animate-pulse'
                }`}
              >
                {activeBatch.status}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2.5">
            {activeBatch.slices.map((slice) => {
              const isInspected =
                slice.run_id === inspectedRunId || (slice.run_id === runId && !inspectedRunId);
              return (
                <button
                  key={slice.run_id}
                  onClick={() => setInspectedRunId(slice.run_id)}
                  className={`p-2.5 rounded-lg border text-left transition-all duration-200 flex flex-col justify-between ${
                    isInspected
                      ? 'bg-sky-950/70 border-sky-500 ring-1 ring-sky-500/50 shadow-md shadow-sky-500/10'
                      : 'bg-slate-950/60 border-slate-800 hover:border-slate-700 hover:bg-slate-900/60'
                  }`}
                >
                  <div className="flex items-center justify-between gap-1.5 mb-1.5">
                    <span
                      className="font-mono text-xs font-bold text-white truncate max-w-[150px]"
                      title={slice.class_name}
                    >
                      {slice.class_name}
                    </span>
                    {isInspected && (
                      <span className="flex items-center gap-1 text-[10px] font-mono font-bold text-sky-300 bg-sky-900/80 px-1.5 py-0.5 rounded border border-sky-700/60 shrink-0">
                        <Eye className="h-2.5 w-2.5" />
                        Active View
                      </span>
                    )}
                  </div>

                  <div className="flex items-center justify-between text-[11px] font-mono">
                    {slice.status === 'RUNNING' && (
                      <span className="flex items-center gap-1 text-sky-400 font-semibold animate-pulse">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        {slice.current_pass ? `Pass ${slice.current_pass}` : 'Running'}
                      </span>
                    )}
                    {slice.status === 'COMPLETED' && (
                      <span className="flex items-center gap-1 text-emerald-400 font-semibold">
                        <CheckCircle2 className="h-3 w-3" />
                        Completed
                      </span>
                    )}
                    {slice.status === 'QUEUED' && (
                      <span className="flex items-center gap-1 text-slate-500">
                        <Clock className="h-3 w-3" />
                        Queued
                      </span>
                    )}
                    {slice.status === 'FAILED' && (
                      <span className="flex items-center gap-1 text-rose-400 font-semibold">
                        <AlertTriangle className="h-3 w-3" />
                        Failed
                      </span>
                    )}

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
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
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

      {/* 3. LIVE TERMINAL VIEWER */}
      <div className="flex-1 flex flex-col bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-2xl min-h-[380px]">
        {/* Terminal HUD & Controls */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900/90 border-b border-slate-800 text-xs font-mono">
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
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0"
              />
              Auto-Scroll
            </label>
          </div>
        </div>

        {/* Monospace Code Stream */}
        <div className="flex-1 p-4 font-mono text-xs overflow-y-auto space-y-1 bg-slate-950/95 leading-relaxed text-slate-300 min-h-[280px]">
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

          <div ref={terminalEndRef} />
        </div>
      </div>

      {/* 4. METRICS & STEP HANDOFF FOOTER */}
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
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

        {/* Auto-Advance Banner & Proceed CTA */}
        <div className="flex items-center gap-3">
          {activeBatch ? (
            activeBatch.status === 'COMPLETED' ||
            activeBatch.status === 'PARTIAL_FAILURE' ||
            isExtractionComplete ? (
              <div className="flex flex-wrap items-center gap-2">
                <div className="px-3 py-1.5 rounded-lg bg-emerald-950/80 border border-emerald-800/80 text-emerald-300 text-xs font-mono flex items-center gap-2">
                  <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
                  <span>
                    All Specs Ready ({activeBatch.completed_slices}/{activeBatch.total_slices})
                  </span>
                </div>

                <button
                  onClick={() => setStep(4)}
                  className="flex items-center gap-2 py-2 px-4 rounded-lg font-bold text-xs text-white bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 shadow-md shadow-emerald-500/20 transition cursor-pointer"
                >
                  <span>Proceed to HITL Review (All Specs Ready)</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-xs font-mono text-slate-400 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-400" />
                <span>
                  Batch Running: {activeBatch.completed_slices} / {activeBatch.total_slices} slices completed (3-worker pool)...
                </span>
              </div>
            )
          ) : isExtractionComplete ? (
            <div className="flex flex-wrap items-center gap-2">
              <div className="px-3 py-1.5 rounded-lg bg-emerald-950/80 border border-emerald-800/80 text-emerald-300 text-xs font-mono flex items-center gap-2">
                <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
                {isAutoAdvancePaused ? (
                  <span>Auto-advance paused</span>
                ) : (
                  <span>
                    Auto-advancing to HITL Review in{' '}
                    <strong className="text-white text-sm">{countdown ?? 2}s</strong>...
                  </span>
                )}
              </div>

              <button
                onClick={handleToggleAutoAdvance}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-xs font-semibold transition"
              >
                {isAutoAdvancePaused ? (
                  <>
                    <Play className="h-3.5 w-3.5 text-emerald-400" />
                    <span>Resume</span>
                  </>
                ) : (
                  <>
                    <Pause className="h-3.5 w-3.5 text-amber-400" />
                    <span>Pause Auto-Advance</span>
                  </>
                )}
              </button>

              <button
                onClick={handleProceedImmediately}
                className="flex items-center gap-2 py-2 px-4 rounded-lg font-bold text-xs text-white bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 shadow-md shadow-emerald-500/20 transition cursor-pointer"
              >
                <span>Proceed Immediately</span>
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-400" />
              <span>Status: Processing multi-pass LLM chain... (Auto-advances to HITL)</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
