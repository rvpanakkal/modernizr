import React, { useRef, useEffect, useState, useMemo } from 'react';
import Editor, { OnMount } from '@monaco-editor/react';
import { useWizardStore } from '../store/wizardStore';
import { FileCode, FileText, CheckCircle2, Link2, Sparkles, AlertCircle } from 'lucide-react';

interface DualMonacoReviewerProps {
  className?: string;
}

export const DualMonacoReviewer: React.FC<DualMonacoReviewerProps> = ({ className = '' }) => {
  const {
    hitlData,
    currentSpec,
    legacySource,
    activeLegacyFile,
    highlightedLines,
    activeScenarioId,
    activeScenarioName,
    editableSpecGherkin,
    editableSpecOpenApi,
    specSha256,
    setActiveLegacyFile,
    selectScenario,
    setEditableSpecGherkin,
    setEditableSpecOpenApi,
  } = useWizardStore();

  const [activeRightTab, setActiveRightTab] = useState<'gherkin' | 'openapi'>('gherkin');

  // Monaco references
  const leftEditorRef = useRef<any>(null);
  const leftMonacoRef = useRef<any>(null);
  const leftDecorationsRef = useRef<string[]>([]);

  const rightEditorRef = useRef<any>(null);
  const rightMonacoRef = useRef<any>(null);

  // Available legacy files list
  const legacyFiles = useMemo(() => {
    if (!hitlData?.legacy_sources) {
      return [activeLegacyFile || 'TransferProcessingService.java'];
    }
    const keys = Object.keys(hitlData.legacy_sources);
    return keys.length > 0 ? keys : [activeLegacyFile || 'TransferProcessingService.java'];
  }, [hitlData, activeLegacyFile]);

  // Scenarios list
  const scenarios = useMemo(() => {
    const spec = currentSpec || hitlData?.spec;
    if (!spec) return [];
    return (spec.bdd_scenarios?.length ? spec.bdd_scenarios : spec.scenarios) || [];
  }, [currentSpec, hitlData]);

  // Left Editor Mount
  const handleLeftMount: OnMount = (editor, monaco) => {
    leftEditorRef.current = editor;
    leftMonacoRef.current = monaco;
    if (highlightedLines) {
      applyLeftHighlight(highlightedLines[0], highlightedLines[1]);
    }
  };

  // Right Editor Mount
  const handleRightMount: OnMount = (editor, monaco) => {
    rightEditorRef.current = editor;
    rightMonacoRef.current = monaco;

    // Listen to cursor movement in Right Editor for scenario traceability
    editor.onDidChangeCursorPosition((e) => {
      if (activeRightTab !== 'gherkin') return;

      const model = editor.getModel();
      if (!model) return;

      const cursorLine = e.position.lineNumber;
      // Scan backwards from cursorLine to find the enclosing Scenario: header
      let matchedTitle: string | null = null;
      for (let l = cursorLine; l >= 1; l--) {
        const lineContent = model.getLineContent(l);
        const match = lineContent.match(/Scenario:\s*(.+)$/i);
        if (match) {
          matchedTitle = match[1].trim();
          break;
        }
      }

      if (matchedTitle) {
        const matchedScenario = scenarios.find(
          (s: any) =>
            (s.title && s.title.trim().toLowerCase() === matchedTitle!.toLowerCase()) ||
            (s.name && s.name.trim().toLowerCase() === matchedTitle!.toLowerCase()) ||
            (s.scenario_id && s.scenario_id === matchedTitle)
        );
        if (matchedScenario) {
          const id = matchedScenario.scenario_id || matchedScenario.title || (matchedScenario as any).name;
          if (id !== activeScenarioId) {
            selectScenario(id);
          }
        }
      }
    });
  };

  // Apply highlight to left editor
  const applyLeftHighlight = (startLine: number, endLine: number) => {
    if (!leftEditorRef.current || !leftMonacoRef.current) return;
    const editor = leftEditorRef.current;
    const monaco = leftMonacoRef.current;

    const newDecorations = [
      {
        range: new monaco.Range(startLine, 1, endLine, 1),
        options: {
          isWholeLine: true,
          className: 'bg-amber-500/20 border-l-4 border-amber-400',
          linesDecorationsClassName: 'bg-amber-400 w-1.5',
          overviewRuler: {
            color: '#f59e0b',
            position: monaco.editor.OverviewRulerLane.Full,
          },
        },
      },
    ];

    leftDecorationsRef.current = editor.deltaDecorations(leftDecorationsRef.current, newDecorations);
    editor.revealLineInCenter(startLine);
  };

  // Synchronize left decorations whenever highlightedLines changes
  useEffect(() => {
    if (highlightedLines) {
      applyLeftHighlight(highlightedLines[0], highlightedLines[1]);
    } else if (leftEditorRef.current) {
      leftDecorationsRef.current = leftEditorRef.current.deltaDecorations(leftDecorationsRef.current, []);
    }
  }, [highlightedLines]);

  // Jump right editor cursor when active scenario changes
  const jumpRightEditorToScenario = (scenario: any) => {
    selectScenario(scenario.scenario_id || scenario.title || scenario.name);
    if (!rightEditorRef.current || activeRightTab !== 'gherkin') return;

    const editor = rightEditorRef.current;
    const model = editor.getModel();
    if (!model) return;

    const targetTitle = (scenario.title || scenario.name || '').toLowerCase();
    const lineCount = model.getLineCount();
    for (let l = 1; l <= lineCount; l++) {
      const lineContent = model.getLineContent(l);
      if (
        lineContent.toLowerCase().includes('scenario:') &&
        lineContent.toLowerCase().includes(targetTitle)
      ) {
        editor.setPosition({ lineNumber: l, column: 1 });
        editor.revealLineInCenter(l);
        break;
      }
    }
  };

  return (
    <div className={`flex flex-col h-full w-full bg-slate-950 rounded-xl border border-slate-800 overflow-hidden shadow-2xl ${className}`}>
      {/* Dual Split Editor Pane */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-slate-800 min-h-[460px]">
        {/* LEFT PANE: Read-Only Legacy Java Source */}
        <div className="flex flex-col h-full bg-slate-900/60">
          {/* Left Editor Header Bar */}
          <div className="flex items-center justify-between px-3.5 py-2.5 bg-slate-900 border-b border-slate-800">
            <div className="flex items-center gap-2 overflow-x-auto scrollbar-none">
              <span className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold uppercase bg-amber-500/10 text-amber-400 border border-amber-500/20 whitespace-nowrap">
                <FileCode className="w-3.5 h-3.5" />
                Legacy Java (Read-Only)
              </span>

              {/* File Selector Tabs */}
              <div className="flex items-center gap-1">
                {legacyFiles.map((fileName) => {
                  const isActive = activeLegacyFile === fileName;
                  return (
                    <button
                      key={fileName}
                      onClick={() => setActiveLegacyFile(fileName)}
                      className={`px-2.5 py-1 text-xs font-mono rounded transition-colors whitespace-nowrap ${
                        isActive
                          ? 'bg-slate-800 text-sky-300 border border-sky-500/30 font-medium'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850'
                      }`}
                    >
                      {fileName}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Traceability Anchor Indicator */}
            {highlightedLines && (
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-[11px] font-mono text-amber-300 animate-pulse">
                <Link2 className="w-3 h-3 text-amber-400" />
                <span>
                  L{highlightedLines[0]}–L{highlightedLines[1]}
                </span>
              </div>
            )}
          </div>

          {/* Left Monaco Editor */}
          <div className="flex-1 relative">
            <Editor
              height="100%"
              language="java"
              value={legacySource || '// Loading legacy source...'}
              theme="vs-dark"
              onMount={handleLeftMount}
              options={{
                readOnly: true,
                minimap: { enabled: false },
                fontSize: 12.5,
                lineNumbers: 'on',
                lineNumbersMinChars: 3,
                glyphMargin: true,
                automaticLayout: true,
                scrollBeyondLastLine: false,
                fontFamily: "'JetBrains Mono', Consolas, 'Courier New', monospace",
                renderLineHighlight: 'all',
                padding: { top: 12, bottom: 12 },
              }}
            />
          </div>
        </div>

        {/* RIGHT PANE: Modern Target Spec (BDD Gherkin & OpenAPI Contract) */}
        <div className="flex flex-col h-full bg-slate-900/60">
          {/* Right Editor Header Bar */}
          <div className="flex items-center justify-between px-3.5 py-2 bg-slate-900 border-b border-slate-800">
            {/* View Mode Switcher Tabs */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => setActiveRightTab('gherkin')}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition ${
                  activeRightTab === 'gherkin'
                    ? 'bg-sky-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                BDD Scenarios (Gherkin)
              </button>
              <button
                onClick={() => setActiveRightTab('openapi')}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition ${
                  activeRightTab === 'openapi'
                    ? 'bg-sky-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                OpenAPI 3.0 Contract
              </button>
            </div>

            {/* SHA-256 Badge */}
            {specSha256 && (
              <div className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-[10px] font-mono text-slate-400">
                <span className="text-slate-500">SHA-256:</span>
                <span className="text-emerald-400 font-bold truncate max-w-[120px]" title={specSha256}>
                  {specSha256.substring(0, 14)}...
                </span>
              </div>
            )}
          </div>

          {/* Right Monaco Editor */}
          <div className="flex-1 relative">
            <Editor
              height="100%"
              language={activeRightTab === 'gherkin' ? 'gherkin' : 'yaml'}
              value={activeRightTab === 'gherkin' ? editableSpecGherkin : editableSpecOpenApi}
              theme="vs-dark"
              onChange={(val) => {
                if (activeRightTab === 'gherkin') {
                  setEditableSpecGherkin(val || '');
                } else {
                  setEditableSpecOpenApi(val || '');
                }
              }}
              onMount={handleRightMount}
              options={{
                readOnly: false,
                minimap: { enabled: false },
                fontSize: 12.5,
                lineNumbers: 'on',
                lineNumbersMinChars: 3,
                glyphMargin: true,
                automaticLayout: true,
                scrollBeyondLastLine: false,
                fontFamily: "'JetBrains Mono', Consolas, 'Courier New', monospace",
                renderLineHighlight: 'all',
                padding: { top: 12, bottom: 12 },
              }}
            />
          </div>
        </div>
      </div>

      {/* Scenario Traceability Bar (Pills Navigation) */}
      {scenarios.length > 0 && (
        <div className="px-3.5 py-2 bg-slate-900 border-t border-slate-800 flex items-center gap-2 overflow-x-auto scrollbar-none">
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1 whitespace-nowrap">
            <Link2 className="w-3 h-3 text-sky-400" />
            Acceptance Scenarios:
          </span>
          <div className="flex items-center gap-1.5">
            {scenarios.map((sc: any) => {
              const scId = sc.scenario_id || sc.title || sc.name;
              const isSelected = activeScenarioId === scId || activeScenarioName === (sc.title || sc.name);
              const anchor = sc.traceability
                ? `L${sc.traceability.start_line}-${sc.traceability.end_line}`
                : '';

              return (
                <button
                  key={scId}
                  onClick={() => jumpRightEditorToScenario(sc)}
                  className={`px-2.5 py-1 text-xs rounded font-mono transition-all flex items-center gap-1.5 whitespace-nowrap ${
                    isSelected
                      ? 'bg-sky-500/20 border border-sky-400 text-sky-200 font-bold shadow-sm'
                      : 'bg-slate-850 hover:bg-slate-800 border border-slate-750 text-slate-300'
                  }`}
                  title={`${sc.title || sc.name} (${anchor})`}
                >
                  <span className="text-sky-400 text-[10px]">{sc.scenario_id || 'SCN'}</span>
                  <span className="truncate max-w-[150px]">{sc.title || sc.name}</span>
                  {anchor && (
                    <span className="text-[10px] text-amber-400/80 bg-amber-500/10 px-1 py-0.2 rounded border border-amber-500/20">
                      {anchor}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
