import React, { useEffect, useState } from 'react';
import { useWizardStore } from '../store/wizardStore';
import { DualMonacoReviewer } from '../components/DualMonacoReviewer';
import {
  ShieldCheck,
  RotateCcw,
  CheckCircle2,
  Lock,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  AlertCircle,
  Hash,
  Layers,
  FileCheck2,
  ChevronDown,
  ChevronUp,
  Tag,
  KeyRound,
  Loader2,
} from 'lucide-react';

export const HitlReviewScreen: React.FC = () => {
  const {
    runId,
    hitlData,
    specSha256,
    activeScenarioName,
    activeScenarioId,
    hitlApproved,
    approvedBy,
    jiraStoryId,
    aggregateRoot,
    jiraEpicKey,
    jiraStoryKey,
    isRevising,
    isApproving,
    hitlError,
    activeProfile,
    fetchHitlData,
    setAggregateRoot,
    setJiraEpicKey,
    setJiraStoryKey,
    submitAiRevision,
    approveAndProceed,
    setStep,
  } = useWizardStore();

  const [isLoading, setIsLoading] = useState(false);
  const [showRevisionModal, setShowRevisionModal] = useState(false);
  const [showArchUnitRules, setShowArchUnitRules] = useState(false);
  const [revisionFeedback, setRevisionFeedback] = useState('');
  const [notification, setNotification] = useState<string | null>(null);

  // Fetch initial HITL review payload
  useEffect(() => {
    if (!hitlData) {
      setIsLoading(true);
      fetchHitlData(runId || 'run-canonical')
        .catch((err) => console.error('Failed to load HITL data:', err))
        .finally(() => setIsLoading(false));
    }
  }, [runId, hitlData, fetchHitlData]);

  const handleTriggerRevision = async () => {
    if (!revisionFeedback.trim()) return;
    try {
      await submitAiRevision(revisionFeedback);
      setShowRevisionModal(false);
      setRevisionFeedback('');
      setNotification('Specification revised successfully by live Claude 3.7 Sonnet.');
    } catch (err: any) {
      console.error('Revision failed:', err);
    }
  };

  const handleApprove = async () => {
    try {
      await approveAndProceed();
      setNotification('Specification approved and gated for Step 5 (Target Synthesis).');
    } catch (err: any) {
      console.error('Approval failed:', err);
    }
  };

  const promptSuggestions = [
    'Add validation for dormant account status before checking limits',
    'Enforce positive transfer amount and daily ceiling checks',
    'Require second-factor authorization for transfers exceeding $10,000',
    'Add idempotency key check to prevent duplicate transfers',
  ];

  return (
    <div className="flex flex-col gap-3.5 flex-1 w-full h-full">
      {/* 1. Header & Step Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-slate-900/80 p-3.5 rounded-xl border border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-sky-400 bg-sky-950/80 px-2 py-0.5 rounded border border-sky-800/60">
              STEP 04
            </span>
            <h2 className="text-lg font-bold text-white tracking-tight">
              Human-in-the-Loop (HITL) Governance & Jira Gate
            </h2>
            {hitlApproved ? (
              <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                APPROVED
              </span>
            ) : (
              <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                <Lock className="w-3.5 h-3.5 text-amber-400" />
                GATE LOCKED
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Audit BDD acceptance criteria against legacy Java EE source. Direct code-to-code translation is strictly forbidden.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowRevisionModal(true)}
            disabled={isRevising || hitlApproved}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 disabled:opacity-50 transition"
          >
            <RotateCcw className="h-3.5 w-3.5 text-sky-400" />
            <span>Request AI Revision</span>
          </button>

          {!hitlApproved ? (
            <button
              onClick={handleApprove}
              disabled={isApproving || isRevising || isLoading}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-600/20 disabled:opacity-50 transition"
            >
              {isApproving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Verifying & Gating...</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="h-4 w-4" />
                  <span>Approve & Gate for Step 5 ▶</span>
                </>
              )}
            </button>
          ) : (
            <button
              onClick={() => setStep(5)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-sky-600 hover:bg-sky-500 shadow-md shadow-sky-600/20 transition"
            >
              <span>Proceed to Synthesis (Step 5)</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* 2. Governance Metadata Bar (Run ID, SHA-256, Aggregate Root, Jira Epic & Story) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-2.5 p-3 bg-slate-900 border border-slate-800 rounded-xl text-xs">
        {/* Run ID & Fingerprint */}
        <div className="flex flex-col gap-1">
          <span className="text-[10px] font-semibold uppercase text-slate-400 flex items-center gap-1">
            <Hash className="w-3 h-3 text-sky-400" />
            Run ID & SHA-256 Hash
          </span>
          <div className="flex items-center gap-2">
            <span className="font-mono font-medium text-slate-200 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
              {hitlData?.run_id || runId || 'run-canonical'}
            </span>
            <span
              className="font-mono text-[11px] text-emerald-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800 truncate cursor-help"
              title={`Full SHA-256: ${specSha256 || 'Pending'}`}
            >
              {(specSha256 || 'SHA-256').substring(0, 12)}...
            </span>
          </div>
        </div>

        {/* DDD Aggregate Root */}
        <div className="flex flex-col gap-1">
          <label htmlFor="aggregate-root-select" className="text-[10px] font-semibold uppercase text-slate-400 flex items-center gap-1">
            <Layers className="w-3 h-3 text-indigo-400" />
            DDD Aggregate Root
          </label>
          <select
            id="aggregate-root-select"
            value={aggregateRoot}
            onChange={(e) => setAggregateRoot(e.target.value)}
            disabled={hitlApproved}
            className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-medium focus:border-sky-500 focus:outline-none"
          >
            <option value="Account">Account (Core Domain)</option>
            <option value="PaymentOrder">PaymentOrder</option>
            <option value="TransferInstruction">TransferInstruction</option>
            <option value="LedgerEntry">LedgerEntry</option>
            <option value="Customer">Customer</option>
          </select>
        </div>

        {/* Jira Epic Key */}
        <div className="flex flex-col gap-1">
          <label htmlFor="jira-epic-key-input" className="text-[10px] font-semibold uppercase text-slate-400 flex items-center gap-1">
            <Tag className="w-3 h-3 text-amber-400" />
            Jira Epic Key
          </label>
          <input
            id="jira-epic-key-input"
            type="text"
            value={jiraEpicKey}
            onChange={(e) => setJiraEpicKey(e.target.value)}
            disabled={hitlApproved}
            placeholder="e.g. MOD-EPIC-12"
            className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 font-mono text-slate-200 focus:border-sky-500 focus:outline-none"
          />
        </div>

        {/* Jira Story Key */}
        <div className="flex flex-col gap-1">
          <label htmlFor="jira-story-key-input" className="text-[10px] font-semibold uppercase text-slate-400 flex items-center gap-1">
            <KeyRound className="w-3 h-3 text-emerald-400" />
            Jira Story Tracking Key
          </label>
          <input
            id="jira-story-key-input"
            type="text"
            value={jiraStoryKey || jiraStoryId}
            onChange={(e) => setJiraStoryKey(e.target.value)}
            disabled={hitlApproved}
            placeholder="e.g. MOD-101"
            className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 font-mono text-slate-200 focus:border-sky-500 focus:outline-none"
          />
        </div>
      </div>

      {/* 3. Notifications & Errors */}
      {hitlError && (
        <div className="flex items-center justify-between p-3 rounded-lg bg-rose-950/70 border border-rose-800 text-rose-200 text-xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{hitlError}</span>
          </div>
        </div>
      )}

      {notification && !hitlError && (
        <div className="flex items-center justify-between p-3 rounded-lg bg-emerald-950/70 border border-emerald-800 text-emerald-200 text-xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{notification}</span>
          </div>
          <button onClick={() => setNotification(null)} className="text-slate-400 hover:text-white">
            ✕
          </button>
        </div>
      )}

      {/* 4. Center Workspace: Dual Synchronized Monaco Editors */}
      <div className="flex-1 min-h-[480px] flex flex-col">
        {isLoading ? (
          <div className="flex-1 flex flex-col items-center justify-center bg-slate-900 border border-slate-800 rounded-xl gap-3">
            <Loader2 className="w-8 h-8 text-sky-400 animate-spin" />
            <span className="text-xs text-slate-400 font-mono">Loading HITL multi-class slice & specification...</span>
          </div>
        ) : (
          <DualMonacoReviewer className="flex-1" />
        )}
      </div>

      {/* 5. Footer Navigation & Governance Status */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-xs">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setStep(3)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-750 text-slate-300 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Telemetry Console</span>
          </button>
          <span className="text-slate-500">|</span>
          <span className="text-slate-400">
            Reviewer:{' '}
            <strong className="text-slate-200">{approvedBy || 'Enterprise Lead Architect'}</strong>
          </span>
        </div>

        <div className="flex items-center gap-3">
          {activeScenarioName && (
            <span className="text-slate-400 font-mono text-[11px] truncate max-w-[280px]">
              Active: <span className="text-sky-300">{activeScenarioName}</span>
            </span>
          )}

          {!hitlApproved ? (
            <button
              onClick={handleApprove}
              disabled={isApproving || isRevising || isLoading}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-600/20 disabled:opacity-50 transition"
            >
              {isApproving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Sealing Receipt...</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="h-4 w-4" />
                  <span>Approve & Gate for Step 5 ▶</span>
                </>
              )}
            </button>
          ) : (
            <button
              onClick={() => setStep(5)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-sky-600 hover:bg-sky-500 shadow-md shadow-sky-600/20 transition"
            >
              <span>Proceed to Synthesis (Step 5)</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* 6. AI Revision Modal */}
      {showRevisionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-slate-750 rounded-2xl w-full max-w-2xl shadow-2xl flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-5 py-4 bg-slate-850 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-sky-400" />
                <h3 className="text-sm font-bold text-white">
                  Targeted Specification Revision (Live Claude 3.7 Sonnet)
                </h3>
              </div>
              <button
                onClick={() => setShowRevisionModal(false)}
                disabled={isRevising}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 flex flex-col gap-4">
              <p className="text-xs text-slate-300 leading-relaxed">
                Provide targeted architect guidance. The cognitive agent chain will surgically re-evaluate
                Pass 2 (business invariants) and Pass 3 (BDD scenarios / OpenAPI contracts), recalibrating
                the cryptographic SHA-256 seal without discarding existing context.
              </p>

              {/* Suggestions */}
              <div className="flex flex-col gap-1.5">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Quick Directives:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {promptSuggestions.map((sug) => (
                    <button
                      key={sug}
                      type="button"
                      onClick={() => setRevisionFeedback(sug)}
                      className="px-2.5 py-1 rounded bg-slate-950 border border-slate-800 hover:border-sky-500/50 text-[11px] text-slate-300 hover:text-sky-200 transition text-left"
                    >
                      {sug}
                    </button>
                  ))}
                </div>
              </div>

              {/* Feedback Textarea */}
              <div className="flex flex-col gap-1.5">
                <label htmlFor="architect-feedback-textarea" className="text-xs font-semibold text-slate-300">
                  Architect Feedback & Rule Adjustments:
                </label>
                <textarea
                  id="architect-feedback-textarea"
                  value={revisionFeedback}
                  onChange={(e) => setRevisionFeedback(e.target.value)}
                  placeholder="e.g. Add validation for dormant account status before checking limits. Require specific 403 Forbidden response."
                  rows={4}
                  disabled={isRevising}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none font-mono"
                />
              </div>

              {/* Strict Zero-Mock Indicator */}
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-sky-950/40 border border-sky-800/40 text-[11px] text-sky-300">
                <ShieldCheck className="w-4 h-4 text-sky-400 shrink-0" />
                <span>
                  <strong>Zero-Mock Pipeline:</strong> Revision executes directly against live Anthropic Claude 3.7. ANTHROPIC_API_KEY must be configured on backend.
                </span>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end gap-2 px-5 py-3.5 bg-slate-850 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setShowRevisionModal(false)}
                disabled={isRevising}
                className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleTriggerRevision}
                disabled={!revisionFeedback.trim() || isRevising}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-sky-600 hover:bg-sky-500 disabled:opacity-50 transition shadow-md shadow-sky-600/20"
              >
                {isRevising ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Executing Claude 3.7 Revision...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Execute Live Revision</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
