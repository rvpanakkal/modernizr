import React, { useEffect, useRef, useState } from 'react';
import { useWizardStore } from '../store/wizardStore';
import { sseClient } from '../services/sseClient';
import {
  Cpu,
  Layers,
  Sparkles,
  ShieldAlert,
  ArrowRight,
  Terminal,
  Activity,
  Zap,
  CheckCircle2,
  Clock,
  Flame,
} from 'lucide-react';

export const TelemetryScreen: React.FC = () => {
  const {
    runId,
    telemetryLogs,
    activePass,
    passStatus,
    totalTokens,
    burnRate,
    isExtractionComplete,
    appendTelemetry,
    setSseConnected,
    setStep,
  } = useWizardStore();

  const terminalEndRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (!runId) return;

    setSseConnected(true);
    sseClient.connect(
      runId,
      (event) => {
        appendTelemetry(event);
      },
      (error) => {
        console.warn('SSE Error:', error);
      }
    );

    return () => {
      sseClient.disconnect();
      setSseConnected(false);
    };
  }, [runId]);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [telemetryLogs, autoScroll]);

  const passes = [
    {
      num: 1,
      name: 'Technical Decompiler',
      status: passStatus.pass1,
      desc: 'Strip Java EE / JSF plumbing, @ManagedBean, container transactions, and trivial getters/setters.',
      metrics: '4 Operations Extracted • 2 Guard Conditions',
    },
    {
      num: 2,
      name: 'Business Rule Abstractor',
      status: passStatus.pass2,
      desc: 'Extract technology-agnostic business rules, validation thresholds, and account constraints.',
      metrics: '4 Business Invariants (BR-001 - BR-004)',
    },
    {
      num: 3,
      name: 'Spec Formatter & BDD',
      status: passStatus.pass3,
      desc: 'Synthesize Gherkin BDD scenarios, data contracts, and bidirectional source line traceability.',
      metrics: '4 BDD Scenarios • Full Trace Matrix',
    },
  ];

  return (
    <div className="flex flex-col gap-5 flex-1 w-full max-w-6xl mx-auto">
      {/* Screen Title */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-sky-400 bg-sky-950/80 px-2 py-0.5 rounded border border-sky-800/60">
              STEP 03
            </span>
            <h2 className="text-xl font-bold text-white tracking-tight">
              Live 3-Pass Cognitive Extraction Console
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Streaming real-time LLM telemetry, token burn rate, and AST decompiler passes over Server-Sent Events (SSE).
          </p>
        </div>

        {isExtractionComplete && (
          <button
            onClick={() => setStep(4)}
            className="flex items-center gap-2 py-2 px-4 rounded-xl font-semibold text-xs text-white bg-emerald-600 hover:bg-emerald-500 shadow-lg shadow-emerald-600/20 animate-bounce transition"
          >
            <span>Proceed to Step 4: HITL Review & Jira Gate</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* 3 Progressive Pass Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {passes.map((p) => {
          const isCurrent = activePass === p.num && p.status === 'running';
          const isDone = p.status === 'completed';
          const isPending = p.status === 'pending';

          return (
            <div
              key={p.num}
              className={`p-4 rounded-xl border flex flex-col justify-between transition-all duration-300 ${
                isCurrent
                  ? 'bg-sky-950/40 border-sky-500 ring-1 ring-sky-500/50 shadow-lg shadow-sky-950/40'
                  : isDone
                  ? 'bg-slate-900 border-slate-800'
                  : 'bg-slate-950/40 border-slate-900 opacity-60'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono font-bold text-sky-400 uppercase tracking-wider">
                    Pass 0{p.num}
                  </span>
                  <span
                    className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full uppercase ${
                      isDone
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : isCurrent
                        ? 'bg-sky-950 text-sky-300 border border-sky-800 animate-pulse'
                        : 'bg-slate-800 text-slate-500'
                    }`}
                  >
                    {p.status}
                  </span>
                </div>
                <h3 className="text-sm font-bold text-white mb-1">{p.name}</h3>
                <p className="text-xs text-slate-400 leading-relaxed">{p.desc}</p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono">
                <span className="text-slate-500">Output:</span>
                <span className="text-sky-300 font-semibold">{isDone ? p.metrics : 'Computing...'}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Telemetry Metrics Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl flex items-center gap-3">
          <div className="p-2 rounded-lg bg-sky-950/80 text-sky-400">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <span className="text-[10px] uppercase font-mono text-slate-500 block">Total Tokens</span>
            <span className="text-sm font-bold font-mono text-white">
              {totalTokens.toLocaleString()}
            </span>
          </div>
        </div>

        <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl flex items-center gap-3">
          <div className="p-2 rounded-lg bg-amber-950/80 text-amber-400">
            <Flame className="h-4 w-4" />
          </div>
          <div>
            <span className="text-[10px] uppercase font-mono text-slate-500 block">Burn Rate</span>
            <span className="text-sm font-bold font-mono text-white">
              {burnRate.toFixed(1)} tok/sec
            </span>
          </div>
        </div>

        <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl flex items-center gap-3">
          <div className="p-2 rounded-lg bg-indigo-950/80 text-indigo-400">
            <Zap className="h-4 w-4" />
          </div>
          <div>
            <span className="text-[10px] uppercase font-mono text-slate-500 block">Protocol</span>
            <span className="text-sm font-bold font-mono text-white">HTTP SSE v1</span>
          </div>
        </div>

        <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-950/80 text-emerald-400">
            <CheckCircle2 className="h-4 w-4" />
          </div>
          <div>
            <span className="text-[10px] uppercase font-mono text-slate-500 block">Status</span>
            <span className="text-sm font-bold font-mono text-emerald-400">
              {isExtractionComplete ? 'EXTRACTION COMPLETE' : 'STREAMING...'}
            </span>
          </div>
        </div>
      </div>

      {/* Terminal Log Console */}
      <div className="flex-1 flex flex-col bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-inner min-h-[380px]">
        {/* Terminal Header */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900 border-b border-slate-800 text-xs">
          <div className="flex items-center gap-2">
            <Terminal className="h-3.5 w-3.5 text-sky-400" />
            <span className="font-mono font-bold text-slate-200">
              Agent Cognitive Chain Telemetry Stream ({telemetryLogs.length} events)
            </span>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400 cursor-pointer">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="rounded bg-slate-800 border-slate-700 text-sky-500 focus:ring-0"
              />
              Auto-scroll
            </label>
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
          </div>
        </div>

        {/* Terminal Stream Body */}
        <div className="flex-1 p-4 font-mono text-xs overflow-y-auto space-y-1.5 max-h-[420px] bg-slate-950/90">
          {telemetryLogs.length === 0 ? (
            <div className="text-slate-600 italic">Waiting for SSE telemetry broadcast...</div>
          ) : (
            telemetryLogs.map((log) => (
              <div key={log.id} className="flex items-start gap-2.5 leading-relaxed">
                <span className="text-slate-600 select-none text-[11px]">
                  {log.timestamp.split('T')[1]?.substring(0, 8)}
                </span>

                {log.pass_number && (
                  <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-slate-800 text-sky-400 border border-slate-700">
                    P{log.pass_number}
                  </span>
                )}

                <span
                  className={
                    log.type === 'EXTRACTION_COMPLETE'
                      ? 'text-emerald-400 font-bold'
                      : log.type === 'HITL_GATE_REACHED'
                      ? 'text-blue-400 font-bold'
                      : log.type === 'PASS_COMPLETED'
                      ? 'text-sky-300 font-semibold'
                      : log.type === 'PASS_STARTED'
                      ? 'text-amber-300 font-semibold'
                      : 'text-slate-300'
                  }
                >
                  {log.log || JSON.stringify(log.raw)}
                </span>

                {log.token_delta && (
                  <span className="text-[10px] text-slate-500 ml-auto select-none">
                    +{log.token_delta} tok
                  </span>
                )}
              </div>
            ))
          )}
          <div ref={terminalEndRef} />
        </div>
      </div>
    </div>
  );
};
