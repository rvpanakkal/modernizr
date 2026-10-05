import React from 'react';
import { useWizardStore } from '../store/wizardStore';
import {
  FileCode2,
  GitBranch,
  Cpu,
  ShieldCheck,
  Sparkles,
  CheckCircle2,
  Lock,
  Radio,
  Server,
  Terminal,
} from 'lucide-react';

interface WizardLayoutProps {
  children: React.ReactNode;
}

const STEPS = [
  { id: 1, title: 'Source Ingestion', subtitle: 'LST Extraction & AST Parsing', icon: FileCode2 },
  { id: 2, title: 'Topology & Slicing', subtitle: 'Graph Discovery & Bound Slice', icon: GitBranch },
  { id: 3, title: 'Cognitive Chain', subtitle: '3-Pass Extraction Console', icon: Cpu },
  { id: 4, title: 'HITL Review & Gate', subtitle: 'Dual-Pane Audit & Jira Sign-off', icon: ShieldCheck },
  { id: 5, title: 'Target Synthesis', subtitle: 'Catalog Reuse & Code Gen', icon: Sparkles },
];

export const WizardLayout: React.FC<WizardLayoutProps> = ({ children }) => {
  const {
    currentStep,
    maxCompletedStep,
    setStep,
    monolithInfo,
    runId,
    sseConnected,
    jiraStoryId,
    hitlApproved,
  } = useWizardStore();

  return (
    <div className="flex flex-col min-h-screen bg-slate-950 text-slate-100">
      {/* Top Application Bar */}
      <header className="sticky top-0 z-50 bg-slate-900/90 backdrop-blur-md border-b border-slate-800 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          {/* Brand & Project Identity */}
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
              <Server className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-base tracking-tight text-white">
                  Enterprise Modernization Factory
                </h1>
                <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-sky-950 text-sky-400 border border-sky-800/60">
                  v2.5 PROD
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono">
                Lossless Semantic Tree (LST) • GraphRAG • Jira HITL Gate
              </p>
            </div>
          </div>

          {/* Telemetry and System Status Badges */}
          <div className="flex items-center gap-3">
            {/* Monolith Info Pill */}
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/60 text-xs">
              <Terminal className="h-3.5 w-3.5 text-slate-400" />
              <span className="text-slate-400">Target:</span>
              <span className="font-mono font-semibold text-slate-200">
                {monolithInfo?.monolithId || 'legacy-banking-monolith'}
              </span>
            </div>

            {/* Run ID Pill */}
            {runId && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-indigo-950/60 border border-indigo-800/60 text-xs">
                <span className="text-indigo-400 font-medium">Run:</span>
                <span className="font-mono font-bold text-indigo-200">{runId}</span>
              </div>
            )}

            {/* Jira Story Badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-950/70 border border-blue-800/60 text-xs shadow-sm">
              <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              <span className="text-blue-300 font-semibold font-mono">{jiraStoryId}</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-900/80 text-blue-200 font-medium">
                {hitlApproved ? 'APPROVED' : 'HITL GATE'}
              </span>
            </div>

            {/* Live SSE Stream Pulse */}
            <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/50 text-xs">
              <Radio
                className={`h-3.5 w-3.5 ${
                  sseConnected ? 'text-emerald-400 animate-pulse' : 'text-slate-500'
                }`}
              />
              <span className="text-[11px] font-mono text-slate-300">
                {sseConnected ? 'STREAM ACTIVE' : 'STREAM STANDBY'}
              </span>
            </div>
          </div>
        </div>

        {/* 5-Step Progressive Navigation Stepper */}
        <div className="max-w-7xl mx-auto mt-4 pt-3 border-t border-slate-800/80">
          <nav className="grid grid-cols-5 gap-2">
            {STEPS.map((step) => {
              const StepIcon = step.icon;
              const isActive = currentStep === step.id;
              const isCompleted = step.id < currentStep || (step.id === 5 && maxCompletedStep >= 5);
              const isAccessible = step.id <= maxCompletedStep + 1;

              return (
                <button
                  key={step.id}
                  onClick={() => isAccessible && setStep(step.id)}
                  disabled={!isAccessible}
                  className={`group relative text-left p-2.5 rounded-xl border transition-all duration-200 flex flex-col justify-between ${
                    isActive
                      ? 'bg-sky-950/40 border-sky-500/70 shadow-lg shadow-sky-900/20 ring-1 ring-sky-500/50'
                      : isCompleted
                      ? 'bg-slate-900/60 border-slate-700/80 hover:bg-slate-800/80 cursor-pointer'
                      : isAccessible
                      ? 'bg-slate-900/30 border-slate-800 hover:bg-slate-800/40 cursor-pointer'
                      : 'bg-slate-950/40 border-slate-900 opacity-40 cursor-not-allowed'
                  }`}
                >
                  <div className="flex items-center justify-between w-full mb-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold font-mono ${
                          isActive
                            ? 'bg-sky-500 text-white shadow-sm'
                            : isCompleted
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {isCompleted ? <CheckCircle2 className="h-3 w-3" /> : step.id}
                      </span>
                      <StepIcon
                        className={`h-4 w-4 ${
                          isActive
                            ? 'text-sky-400'
                            : isCompleted
                            ? 'text-emerald-400'
                            : 'text-slate-400 group-hover:text-slate-200'
                        }`}
                      />
                    </div>
                    {!isAccessible && <Lock className="h-3 w-3 text-slate-600" />}
                  </div>

                  <div>
                    <h3
                      className={`text-xs font-semibold truncate ${
                        isActive
                          ? 'text-sky-200 font-bold'
                          : isCompleted
                          ? 'text-slate-200'
                          : 'text-slate-400'
                      }`}
                    >
                      {step.title}
                    </h3>
                    <p className="text-[10px] text-slate-500 truncate hidden sm:block">
                      {step.subtitle}
                    </p>
                  </div>

                  {/* Active bottom accent bar */}
                  {isActive && (
                    <div className="absolute -bottom-[13px] left-0 right-0 h-[2px] bg-sky-400 rounded-full" />
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      {/* Main Screen Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 flex flex-col">
        {children}
      </main>

      {/* Auditable Invariant Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 px-6 py-2.5 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Primary Directive: <strong>Code-to-Spec-to-Code Enforced</strong>
            </span>
            <span className="hidden md:inline text-slate-600">•</span>
            <span className="hidden md:inline text-slate-400">
              Architectural Invariant: Pointer & Receipt Pattern (SHA-256 Verified)
            </span>
          </div>
          <div className="font-mono text-[11px] text-slate-500">
            Jira Spec Gate: Step 4 HITL Checkpoint Required Before Step 5 Synthesis
          </div>
        </div>
      </footer>
    </div>
  );
};
