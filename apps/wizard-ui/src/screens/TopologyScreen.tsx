import React, { useEffect, useState, useMemo } from 'react';
import { useWizardStore } from '../store/wizardStore';
import { EntryPoint, GraphNode, LayerType } from '../types/graph';
import { CytoscapeGraph } from '../components/CytoscapeGraph';
import {
  Layers,
  ArrowRight,
  Sliders,
  Gauge,
  CheckCircle,
  AlertTriangle,
  Info,
  GitCommit,
  Search,
  X,
  FileCode,
  ChevronRight,
  Loader2,
  FolderOpen,
  ArrowLeft,
  AlertCircle,
} from 'lucide-react';

export const TopologyScreen: React.FC = () => {
  const {
    entrypoints,
    selectedEntryPoint,
    selectEntryPoint,
    sliceDepth,
    setSliceDepth,
    sliceData,
    selectedNode,
    setSelectedNode,
    fetchEntrypoints,
    proceedToExtraction,
    isGraphLoading,
    graphError,
    setStep,
  } = useWizardStore();

  const [searchQuery, setSearchQuery] = useState('');
  const [activeLayerFilter, setActiveLayerFilter] = useState<'ALL' | 'PRESENTATION' | 'API' | 'INTEGRATION'>('ALL');
  const [localDepth, setLocalDepth] = useState<number>(sliceDepth || 5);
  const [isExtracting, setIsExtracting] = useState(false);

  // Load entrypoints on mount if not yet populated
  useEffect(() => {
    fetchEntrypoints();
  }, [fetchEntrypoints]);

  // Sync local depth when store changes from outside
  useEffect(() => {
    setLocalDepth(sliceDepth);
  }, [sliceDepth]);

  // Debounce depth slider changes to avoid API thrashing
  useEffect(() => {
    if (localDepth === sliceDepth) return;
    const timer = setTimeout(() => {
      setSliceDepth(localDepth);
    }, 280);
    return () => clearTimeout(timer);
  }, [localDepth, sliceDepth, setSliceDepth]);

  const handleSelectEntrypoint = (entry: EntryPoint) => {
    selectEntryPoint(entry);
  };

  const handleProceed = async () => {
    if (!selectedEntryPoint || !sliceData || isGraphLoading || isExtracting) return;
    setIsExtracting(true);
    try {
      await proceedToExtraction();
    } finally {
      setIsExtracting(false);
    }
  };

  // Filter entry points by search query and layer tab
  const filteredEntrypoints = useMemo(() => {
    return entrypoints.filter((ep) => {
      const epLayer = (ep.layer || 'PRESENTATION').toUpperCase();
      const matchesLayer = activeLayerFilter === 'ALL' || epLayer === activeLayerFilter;
      const q = searchQuery.trim().toLowerCase();
      const className = ep.class_name || ep.simple_name || '';
      const fqn = ep.fqn || '';
      const annotations = ep.annotations || [];
      const matchesSearch =
        !q ||
        className.toLowerCase().includes(q) ||
        fqn.toLowerCase().includes(q) ||
        annotations.some((a) => a.toLowerCase().includes(q));
      return matchesLayer && matchesSearch;
    });
  }, [entrypoints, activeLayerFilter, searchQuery]);

  const estimatedTokens = sliceData?.estimated_tokens || 0;
  const maxTokens = 6000;
  const tokenPercentage = Math.min(Math.round((estimatedTokens / maxTokens) * 100), 100);
  const isOverBudget = estimatedTokens > maxTokens;

  const getTokenBarColor = () => {
    if (estimatedTokens < 4000) return 'bg-emerald-500';
    if (estimatedTokens <= 5500) return 'bg-amber-500';
    return 'bg-rose-500';
  };

  const getTokenTextColor = () => {
    if (estimatedTokens < 4000) return 'text-emerald-400';
    if (estimatedTokens <= 5500) return 'text-amber-400';
    return 'text-rose-400';
  };

  // Graceful empty state when no LST graph data is present
  if (entrypoints.length === 0 && !isGraphLoading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 h-full w-full max-w-4xl mx-auto py-16 px-4 text-center">
        <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center mb-4 text-sky-400 shadow-xl shadow-sky-950/40">
          <FolderOpen className="h-8 w-8" />
        </div>
        <h2 className="text-xl font-bold text-white mb-2">No In-Memory Graph Populated</h2>
        <p className="text-sm text-slate-400 max-w-md mb-6 leading-relaxed">
          The NetworkX in-memory topology engine requires parsed Java EE metadata. Please upload your legacy codebase archive or a pre-computed LST JSON file in Step 1.
        </p>
        <button
          onClick={() => setStep(1)}
          className="flex items-center gap-2 py-2.5 px-5 rounded-xl font-semibold text-xs text-white bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-600 hover:to-indigo-700 shadow-lg shadow-sky-500/20 transition"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Return to Source Ingestion (Step 01)</span>
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 flex-1 h-full w-full max-w-7xl mx-auto">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-sky-400 bg-sky-950/80 px-2 py-0.5 rounded border border-sky-800/60">
              STEP 02
            </span>
            <h2 className="text-xl font-bold text-white tracking-tight">
              Topology Discovery & Vertical Slicing
            </h2>
            {isGraphLoading && (
              <span className="flex items-center gap-1.5 text-xs text-sky-400 font-mono bg-sky-950/60 px-2 py-0.5 rounded border border-sky-800/40 animate-pulse">
                <Loader2 className="h-3 w-3 animate-spin" />
                Querying Graph...
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Query in-memory NetworkX store for UI entrypoints, traverse dependency paths, and bound execution slices under 6,000 tokens.
          </p>
        </div>

        <button
          onClick={handleProceed}
          disabled={!sliceData || isExtracting || isGraphLoading || isOverBudget || !selectedEntryPoint}
          className="flex items-center gap-2 py-2 px-4 rounded-xl font-semibold text-xs text-white bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-600 hover:to-indigo-700 shadow-md shadow-sky-500/20 disabled:opacity-50 transition cursor-pointer disabled:cursor-not-allowed"
        >
          {isExtracting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Extracting Slice...</span>
            </>
          ) : (
            <>
              <span>Extract Vertical Slice & Proceed</span>
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </div>

      {/* Graph Error Alert */}
      {graphError && (
        <div className="p-3 bg-rose-950/70 border border-rose-800/80 rounded-xl text-xs text-rose-300 flex items-center justify-between gap-2 shadow-sm">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
            <span className="font-mono">{graphError}</span>
          </div>
          <button
            onClick={() => fetchEntrypoints()}
            className="text-xs font-bold text-rose-200 hover:text-white underline underline-offset-2 shrink-0 font-mono"
          >
            Retry Query
          </button>
        </div>
      )}

      {/* Main 3-Column Interactive Layout */}
      <div className="grid grid-cols-12 gap-4 flex-1 min-h-[600px]">
        {/* Column 1: Entry-Point Catalog */}
        <div className="col-span-12 lg:col-span-3 bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col gap-3 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5 text-sky-400" />
              Entrypoint Catalog ({entrypoints.length})
            </span>
          </div>

          {/* Search Filter */}
          <div className="relative">
            <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search class name or FQN..."
              className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-7 py-1.5 text-xs text-white font-mono placeholder:text-slate-600 focus:outline-none focus:border-sky-500"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-2 text-slate-500 hover:text-slate-300"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>

          {/* Filter Chips */}
          <div className="flex items-center p-0.5 bg-slate-950 rounded-lg border border-slate-800 text-[10px] font-mono">
            {[
              { id: 'ALL', label: 'All' },
              { id: 'PRESENTATION', label: 'UI' },
              { id: 'API', label: 'API' },
              { id: 'INTEGRATION', label: 'Gateway' },
            ].map((chip) => (
              <button
                key={chip.id}
                onClick={() => setActiveLayerFilter(chip.id as any)}
                className={`flex-1 py-1 rounded text-center transition ${
                  activeLayerFilter === chip.id
                    ? 'bg-sky-600 text-white font-bold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {chip.label}
              </button>
            ))}
          </div>

          {/* Entrypoint List */}
          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {filteredEntrypoints.length > 0 ? (
              filteredEntrypoints.map((entry) => {
                const isSelected = selectedEntryPoint?.fqn === entry.fqn;
                const displayName = entry.class_name || entry.simple_name || entry.fqn.split('.').pop();
                const marker = entry.framework_marker || (entry.annotations && entry.annotations[0]) || '@ManagedBean';
                const methodCount = entry.method_count ?? (entry as any).methods_count ?? 0;
                const lineCount = entry.line_count ?? 0;

                return (
                  <button
                    key={entry.fqn}
                    onClick={() => handleSelectEntrypoint(entry)}
                    className={`w-full p-2.5 rounded-lg border text-left transition flex flex-col gap-1.5 ${
                      isSelected
                        ? 'bg-sky-950/70 border-sky-500 text-sky-200 ring-1 ring-sky-500/50'
                        : 'bg-slate-950/80 border-slate-800 text-slate-300 hover:bg-slate-800/40 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-mono text-xs font-bold truncate">
                        {displayName}
                      </span>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 shrink-0 font-medium">
                        {entry.layer}
                      </span>
                    </div>

                    <span className="text-[10px] text-slate-500 font-mono truncate">
                      {entry.fqn}
                    </span>

                    <div className="flex items-center justify-between gap-1 pt-0.5 text-[10px] font-mono text-slate-400">
                      <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700/60 text-amber-300">
                        {marker.startsWith('@') ? marker : `@${marker}`}
                      </span>
                      <div className="flex items-center gap-2 text-slate-500 text-[10px]">
                        <span>{methodCount} methods</span>
                        {lineCount > 0 && <span>• {lineCount} lines</span>}
                      </div>
                    </div>
                  </button>
                );
              })
            ) : (
              <div className="py-12 text-center text-slate-500 text-xs font-mono">
                No entry points match filter criteria.
              </div>
            )}
          </div>
        </div>

        {/* Column 2: Topology Canvas & HUD */}
        <div className="col-span-12 lg:col-span-6 flex flex-col gap-2 bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-sm">
          {/* Top Status Bar */}
          <div className="flex items-center justify-between px-2 py-1.5 border-b border-slate-800/80 text-xs font-mono">
            <div className="flex items-center gap-1.5 text-slate-400 truncate">
              <GitCommit className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
              <span>Root:</span>
              <strong className="text-sky-300 font-bold truncate">
                {selectedEntryPoint?.class_name || selectedEntryPoint?.simple_name || 'Select Entry Point'}
              </strong>
              <ChevronRight className="h-3 w-3 text-slate-600 shrink-0" />
              <span>{localDepth} Hops</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[11px] text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                {sliceData?.total_nodes ?? sliceData?.nodes?.length ?? 0} Nodes / {sliceData?.total_edges ?? sliceData?.edges?.length ?? 0} Edges
              </span>
            </div>
          </div>

          {/* Cytoscape Canvas */}
          <div className="flex-1 w-full h-full relative rounded-lg overflow-hidden border border-slate-800/80 min-h-[460px]">
            <CytoscapeGraph
              nodes={sliceData?.nodes || []}
              edges={sliceData?.edges || []}
              selectedNodeId={selectedNode?.id}
              onNodeSelect={setSelectedNode}
            />
          </div>
        </div>

        {/* Column 3: Slice Governance & Node Inspector */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-4 bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm overflow-y-auto max-h-[720px]">
          {/* Depth Control (1 to 8 hops with debounced dispatch) */}
          <div className="flex flex-col gap-2 pb-3 border-b border-slate-800">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white font-mono flex items-center gap-1.5">
                <Sliders className="h-3.5 w-3.5 text-sky-400" />
                Traversal Depth: {localDepth} Hops
              </span>
              <span className="text-[10px] text-slate-500 font-mono">1 to 8 hops</span>
            </div>
            <input
              type="range"
              min="1"
              max="8"
              value={localDepth}
              onChange={(e) => setLocalDepth(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-950 rounded-lg appearance-none cursor-pointer accent-sky-500"
            />
          </div>

          {/* Token Budget Gauge: estimated_tokens / 6,000 */}
          <div className="flex flex-col gap-2 p-3 bg-slate-950 rounded-lg border border-slate-800">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5 font-mono">
                <Gauge className="h-3.5 w-3.5 text-sky-400" />
                Token Budget Gauge
              </span>
              <span className={`text-xs font-mono font-bold ${getTokenTextColor()}`}>
                {estimatedTokens.toLocaleString()} / {maxTokens.toLocaleString()}
              </span>
            </div>

            <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${getTokenBarColor()}`}
                style={{ width: `${tokenPercentage}%` }}
              />
            </div>

            <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
              <span>{tokenPercentage}% of budget</span>
              {isOverBudget ? (
                <span className="text-rose-400 flex items-center gap-1 font-bold">
                  <AlertTriangle className="h-2.5 w-2.5" />
                  Budget Exceeded
                </span>
              ) : (
                <span className="text-emerald-400 flex items-center gap-1">
                  <CheckCircle className="h-2.5 w-2.5" />
                  Within 6k Budget
                </span>
              )}
            </div>

            {isOverBudget && (
              <div className="mt-1 p-2.5 rounded bg-rose-950/80 border border-rose-800 text-[10px] text-rose-300 flex items-start gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5 text-rose-400" />
                <span>
                  Slice exceeds the 6,000-token ceiling ({estimatedTokens.toLocaleString()} tokens). Please decrease traversal depth hops to prevent LLM cognitive overflow.
                </span>
              </div>
            )}
          </div>

          {/* Active Node Inspector Card */}
          <div className="flex flex-col gap-2 flex-1">
            <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-1.5">
              <Info className="h-3.5 w-3.5 text-sky-400" />
              Node Inspector
            </span>

            {selectedNode ? (
              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs font-mono flex flex-col gap-2.5">
                <div>
                  <span className="text-slate-500 text-[10px] block">Component Name:</span>
                  <span className="font-bold text-white text-sm">
                    {selectedNode.label || selectedNode.name || selectedNode.id.split('.').pop()}
                  </span>
                </div>

                <div>
                  <span className="text-slate-500 text-[10px] block">Fully Qualified Name:</span>
                  <span className="text-sky-300 break-all text-[11px]">{selectedNode.id}</span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-slate-500 text-[10px] block">Layer:</span>
                    <span className="text-slate-200 font-semibold">{selectedNode.layer}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] block">Line Range:</span>
                    <span className="text-slate-300">
                      {selectedNode.start_line != null && selectedNode.end_line != null
                        ? `L${selectedNode.start_line} - L${selectedNode.end_line}`
                        : 'N/A'}
                    </span>
                  </div>
                </div>

                {selectedNode.file_path && (
                  <div>
                    <span className="text-slate-500 text-[10px] block">File Location:</span>
                    <span className="text-slate-300 text-[11px] truncate block" title={selectedNode.file_path}>
                      {selectedNode.file_path}
                    </span>
                  </div>
                )}

                {selectedNode.annotations && selectedNode.annotations.length > 0 && (
                  <div>
                    <span className="text-slate-500 text-[10px] block">Annotations:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {selectedNode.annotations.map((a) => (
                        <span
                          key={a}
                          className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-amber-300 text-[10px]"
                        >
                          {a.startsWith('@') ? a : `@${a}`}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {selectedNode.methods && selectedNode.methods.length > 0 && (
                  <div>
                    <span className="text-slate-500 text-[10px] block">Declared Methods ({selectedNode.methods.length}):</span>
                    <div className="flex flex-col gap-0.5 mt-1 text-[11px] text-slate-300 max-h-[140px] overflow-y-auto pr-1">
                      {selectedNode.methods.map((m) => (
                        <div key={m} className="truncate">
                          • {m}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {selectedNode.source_code && (
                  <div>
                    <span className="text-slate-500 text-[10px] block">Source Snippet:</span>
                    <pre className="mt-1 p-2 bg-slate-900 rounded border border-slate-800 text-[10px] text-slate-300 overflow-x-auto max-h-[120px]">
                      {selectedNode.source_code}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-4 bg-slate-950 rounded-lg border border-slate-800/80 text-center text-slate-500 text-xs py-8 font-mono">
                Click any node in the topology canvas to inspect methods, annotations, and parameters.
              </div>
            )}
          </div>

          {/* Action Footer Button */}
          <div className="pt-2 border-t border-slate-800">
            <button
              onClick={handleProceed}
              disabled={!sliceData || isExtracting || isGraphLoading || isOverBudget || !selectedEntryPoint}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg font-semibold text-xs text-white bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-600 hover:to-indigo-700 shadow-md shadow-sky-500/20 disabled:opacity-50 transition cursor-pointer disabled:cursor-not-allowed"
            >
              {isExtracting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Extracting Vertical Slice...</span>
                </>
              ) : (
                <>
                  <span>Extract Vertical Slice & Proceed</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
