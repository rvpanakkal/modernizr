import React, { useEffect, useState } from 'react';
import { useWizardStore } from '../store/wizardStore';
import { apiClient } from '../services/api';
import { MonacoViewer } from '../components/MonacoViewer';
import {
  ShieldCheck,
  RotateCcw,
  CheckCircle2,
  Lock,
  ArrowRight,
  FileCheck2,
  Sparkles,
  AlertCircle,
  MessageSquare,
  ListTree,
  ExternalLink,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

export const HitlReviewScreen: React.FC = () => {
  const {
    runId,
    specData,
    legacySource,
    specSha256,
    highlightedLines,
    activeScenarioName,
    hitlApproved,
    approvedBy,
    jiraStoryId,
    activeProfile,
    setSpecData,
    updateSpecData,
    setHighlightedLines,
    setActiveScenarioName,
    setHitlApproved,
    setStep,
  } = useWizardStore();

  const [isLoading, setIsLoading] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [showRevisionModal, setShowRevisionModal] = useState(false);
  const [showArchUnitRules, setShowArchUnitRules] = useState(false);
  const [revisionFeedback, setRevisionFeedback] = useState('');
  const [approverName, setApproverName] = useState('Enterprise Lead Architect');
  const [editableSpecText, setEditableSpecText] = useState('');
  const [notification, setNotification] = useState<string | null>(null);

  // Load specification if not already in store
  useEffect(() => {
    const loadSpec = async () => {
      const activeRunId = runId || 'run-canonical';
      setIsLoading(true);
      try {
        const res = await apiClient.getSpec(activeRunId);
        setSpecData(res.spec, res.legacy_source, res.spec_sha256, res.hitl_approved);
        // Format spec as readable markdown/Gherkin
        const formatted = formatSpecToMarkdown(res.spec);
        setEditableSpecText(formatted);
      } catch (err) {
        console.error('Failed to load spec for review:', err);
      } finally {
        setIsLoading(false);
      }
    };

    if (!specData || !legacySource) {
      loadSpec();
    } else {
      setEditableSpecText(formatSpecToMarkdown(specData));
    }
  }, [runId]);

  const formatSpecToMarkdown = (spec: any): string => {
    if (!spec) return '';
    let md = `# Feature: ${spec.feature_name || 'Modernized Feature'}\n`;
    md += `Domain: ${spec.domain || 'Core Banking'} | Tracking: ${spec.jira_story_id || jiraStoryId}\n\n`;
    md += `## Business Summary\n${spec.business_summary || ''}\n\n`;

    md += `## Technology-Agnostic Business Rules\n`;
    if (spec.business_rules) {
      spec.business_rules.forEach((rule: any) => {
        md += `### [${rule.rule_id}] ${rule.description}\n`;
        md += `- **Type**: ${rule.rule_type}\n`;
        md += `- **Condition**: ${rule.condition}\n`;
        md += `- **Action**: ${rule.action_or_outcome}\n`;
        if (rule.legacy_refs?.length) {
          md += `- **Legacy Ref**: \`${rule.legacy_refs.join(', ')}\`\n`;
        }
        md += `\n`;
      });
    }

    md += `## Acceptance Scenarios (Gherkin BDD)\n`;
    if (spec.scenarios) {
      spec.scenarios.forEach((sc: any) => {
        md += `### Scenario: ${sc.name}\n`;
        sc.given?.forEach((g: string) => (md += `  Given ${g}\n`));
        md += `  When ${sc.when}\n`;
        sc.then?.forEach((t: string) => (md += `  Then ${t}\n`));
        if (sc.legacy_refs?.length) {
          md += `  # Traceability: ${sc.legacy_refs.join(', ')}\n`;
        }
        md += `\n`;
      });
    }

    md += `## Target Contract Fields\n`;
    if (spec.data_contract_fields) {
      Object.entries(spec.data_contract_fields).forEach(([k, v]) => {
        md += `- **${k}**: \`${v}\`\n`;
      });
    }

    return md;
  };

  const handleScenarioClick = (scenario: any) => {
    setActiveScenarioName(scenario.name);

    // Parse legacy ref lines (e.g., L36-L38 or L65-L71)
    const ref = scenario.legacy_refs?.[0] || '';
    const match = ref.match(/:L(\d+)(?:-L(\d+))?/);
    if (match) {
      const startLine = parseInt(match[1], 10);
      const endLine = match[2] ? parseInt(match[2], 10) : startLine;
      setHighlightedLines([startLine, endLine]);
    } else {
      setHighlightedLines(null);
    }
  };

  const handleApprove = async () => {
    const activeRunId = runId || 'run-canonical';
    setIsApproving(true);
    try {
      const res = await apiClient.approveHitl(
        activeRunId,
        approverName,
        'Analyst audit completed. Specifications verified against legacy source.',
        specSha256
      );
      setHitlApproved(true, approverName);
      setNotification(`Jira issue ${res.jira_story_id} transitioned to APPROVED_FOR_SYNTHESIS.`);
    } catch (err: any) {
      console.error('Approval failed:', err);
      setNotification('Approval failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsApproving(false);
    }
  };

  const handleTriggerRevision = async () => {
    if (!revisionFeedback.trim()) return;
    const activeRunId = runId || 'run-canonical';
    setIsLoading(true);
    try {
      const res = await apiClient.reviseHitl(activeRunId, revisionFeedback, 2);
      updateSpecData(res.revised_spec, res.spec_sha256);
      setEditableSpecText(formatSpecToMarkdown(res.revised_spec));
      setShowRevisionModal(false);
      setRevisionFeedback('');
      setNotification('Specification revised successfully by AI agent.');
    } catch (err: any) {
      console.error('Revision failed:', err);
      setNotification('Revision request failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 flex-1 w-full h-full">
      {/* Step Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-sky-400 bg-sky-950/80 px-2 py-0.5 rounded border border-sky-800/60">
              STEP 04
            </span>
            <h2 className="text-xl font-bold text-white tracking-tight">
              HITL Spec Review & Jira Gate Checkpoint
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Audit Gherkin acceptance criteria against legacy Java EE source. Human approval unblocks Step 5 target synthesis.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowRevisionModal(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            <RotateCcw className="h-3.5 w-3.5 text-sky-400" />
            <span>Request AI Revision</span>
          </button>

          {!hitlApproved ? (
            <button
              onClick={handleApprove}
              disabled={isApproving}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-600/20 disabled:opacity-50 transition"
            >
              <ShieldCheck className="h-4 w-4" />
              <span>{isApproving ? 'Verifying Receipt...' : 'Approve & Sync to Jira'}</span>
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

      {/* Architecture Governance & Invariant Rules Bar */}
      <div className="flex flex-col gap-2 p-3 bg-slate-900 border border-slate-800 rounded-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {/* Governance Badges */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-800/60">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              <span>Target Profile: {activeProfile?.name || 'Enterprise-Spring-Boot-3.5-Standard'}</span>
            </span>

            <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-950 text-sky-300 border border-slate-800">
              Pkg: {activeProfile?.base_package_pattern || 'com.enterprise.{domain}.v2'}
            </span>

            {activeProfile?.sha256_hash && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono bg-slate-950 text-slate-400 border border-slate-800">
                <span className="text-slate-500">SHA-256:</span>
                <span className="text-slate-300 font-bold">
                  {activeProfile.sha256_hash.slice(0, 10)}...
                </span>
              </span>
            )}
          </div>

          {/* ArchUnit Accordion Toggle */}
          <button
            type="button"
            onClick={() => setShowArchUnitRules(!showArchUnitRules)}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-slate-950 hover:bg-slate-800 text-slate-300 border border-slate-800 transition"
          >
            <ShieldCheck className="h-3.5 w-3.5 text-sky-400" />
            <span>
              {showArchUnitRules
                ? 'Hide Architecture Invariants'
                : `Enforced Invariants (${activeProfile?.conformance_rules?.length || 4} ArchUnit Rules)`}
            </span>
            {showArchUnitRules ? (
              <ChevronUp className="h-3.5 w-3.5 text-slate-400" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
            )}
          </button>
        </div>

        {/* ArchUnit Rules Accordion / Drawer */}
        {showArchUnitRules && (
          <div className="mt-2 pt-3 border-t border-slate-800/80 flex flex-col gap-2.5">
            <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
              <span className="font-semibold text-slate-200">
                Step 5.5 ArchUnit Conformance Gate Invariants
              </span>
              <span>All target classes must satisfy these deterministic assertions</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {(activeProfile?.conformance_rules || []).map((rule) => (
                <div
                  key={rule.rule_id}
                  className="p-3 bg-slate-950 rounded-lg border border-slate-800 flex flex-col gap-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-sky-950 text-sky-300 border border-sky-800">
                      {rule.rule_id}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500 truncate max-w-[200px]">
                      {rule.test_method_name}
                    </span>
                  </div>
                  <p className="text-xs text-slate-200">{rule.description}</p>
                  <pre className="p-1.5 bg-slate-900 rounded text-[10px] font-mono text-emerald-400 overflow-x-auto border border-slate-800/80">
                    {rule.rule_code}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {notification && (
        <div className="flex items-center justify-between p-3 rounded-lg bg-sky-950/60 border border-sky-800 text-sky-200 text-xs">
          <span>{notification}</span>
          <button onClick={() => setNotification(null)} className="text-slate-400 hover:text-white">
            ✕
          </button>
        </div>
      )}

      {/* Traceability Quick Selector Chips */}
      {specData?.scenarios && (
        <div className="flex items-center gap-2 p-2 bg-slate-900 border border-slate-800 rounded-xl overflow-x-auto text-xs">
          <span className="text-[11px] font-mono text-slate-500 uppercase tracking-wider shrink-0 px-2 flex items-center gap-1">
            <ListTree className="h-3.5 w-3.5 text-sky-400" />
            Trace Links:
          </span>
          {specData.scenarios.map((sc) => {
            const isSelected = activeScenarioName === sc.name;
            return (
              <button
                key={sc.name}
                onClick={() => handleScenarioClick(sc)}
                className={`px-3 py-1 rounded-lg font-mono text-[11px] whitespace-nowrap transition border ${
                  isSelected
                    ? 'bg-sky-500 text-white border-sky-400 font-bold shadow-sm'
                    : 'bg-slate-950 text-slate-300 border-slate-800 hover:border-slate-700'
                }`}
              >
                {sc.name}
              </button>
            );
          })}
        </div>
      )}

      {/* Dual Synchronized Monaco Editors */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-[500px]">
        {/* Left Pane: Read-only Legacy Java Source */}
        <div className="h-full flex flex-col">
          <MonacoViewer
            title="Legacy Java Source (EJB / JSF Slice)"
            badge="Read-Only Ground Truth"
            language="java"
            value={legacySource}
            readOnly={true}
            highlightRange={highlightedLines}
          />
        </div>

        {/* Right Pane: Editable Gherkin / Specification */}
        <div className="h-full flex flex-col">
          <MonacoViewer
            title="Modernized Gherkin Specification & Data Contract"
            badge="HITL Editable"
            language="markdown"
            value={editableSpecText}
            onChange={(val) => setEditableSpecText(val || '')}
            sha256={specSha256}
          />
        </div>
      </div>

      {/* AI Revision Modal */}
      {showRevisionModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-sky-400" />
              <h3 className="font-bold text-base text-white">Request AI Spec Revision</h3>
            </div>
            <p className="text-xs text-slate-400">
              Provide feedback or specify business constraints to re-prompt the cognitive chain (Pass 2 & Pass 3).
            </p>

            <textarea
              rows={4}
              value={revisionFeedback}
              onChange={(e) => setRevisionFeedback(e.target.value)}
              placeholder="e.g., Add rule enforcing high-risk AML compliance flagging for transfers greater than $10,000.00."
              className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-sky-500 font-mono"
            />

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => setShowRevisionModal(false)}
                className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleTriggerRevision}
                disabled={!revisionFeedback.trim() || isLoading}
                className="px-4 py-2 rounded-lg text-xs font-semibold text-white bg-sky-600 hover:bg-sky-500 shadow-md shadow-sky-600/20 disabled:opacity-50"
              >
                {isLoading ? 'Re-prompting Agent...' : 'Submit AI Revision'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
