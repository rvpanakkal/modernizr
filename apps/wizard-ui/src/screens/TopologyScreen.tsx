import React, { useEffect, useState } from 'react';
import { useWizardStore, EntrypointItem, GraphNode } from '../store/wizardStore';
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
  ShieldCheck,
  ChevronRight,
  Activity,
  Maximize2,
  Code2,
} from 'lucide-react';

export const TopologyScreen: React.FC = () => {
  const {
    entrypoints,
    selectedEntrypoint,
    selectEntryPoint,
    sliceDepth,
    setSliceDepth,
    sliceData,
    selectedNode,
    setSelectedNode,
    fetchEntryPoints,
    extractAndProceed,
    isLoading,
  } = useWizardStore();

  const [searchQuery, setSearchQuery] = useState('');
  const [activeLayerTab, setActiveLayerTab] = useState<'ALL' | 'Presentation' | 'API' | 'Integration'>('ALL');
  const [isExtracting, setIsExtracting] = useState(false);

  useEffect(() => {
    fetchEntryPoints();
  }, [fetchEntryPoints]);

  const handleSelectEntrypoint = (entry: EntrypointItem) => {
    selectEntryPoint(entry);
  };

  const handleDepthChange = (newDepth: number) => {
    setSliceDepth(newDepth);
  };

  const handleProceed = async () => {
    if (!selectedEntrypoint || !sliceData) return;
    setIsExtracting(true);
    try {
      await extractAndProceed();
    } finally {
      setIsExtracting(false);
    }
  };

  // Filter entry points by search query and layer tab
  const filteredEntrypoints = entrypoints.filter((ep) => {
    const matchesLayer = activeLayerTab === 'ALL' || ep.layer.toUpperCase() === activeLayerTab.toUpperCase();
    const q = searchQuery.trim().toLowerCase();
    const matchesSearch =
      !q ||
      ep.simple_name.toLowerCase().includes(q) ||
      ep.fqn.toLowerCase().includes(q) ||
      ep.annotations.some((a) => a.toLowerCase().includes(q));
    return matchesLayer && matchesSearch;
  });

  const estimatedTokens = sliceData?.estimated_tokens || 1420;
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
              Topology Discovery & Slice Bounding
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Query in-memory NetworkX graph for presentation entry-points, traverse INJECTS & CALLS edges, and bound execution slices under 6,000 tokens.
          </p>
        </div>

        <button
          onClick={handleProceed}
          disabled={!sliceData || isExtracting || isOverBudget || !selectedEntrypoint}
          className="flex items-center gap-2 py-2 px-4 rounded-xl font-semibold text-xs text-white bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-600 hover:to-indigo-700 shadow-md shadow-sky-500/20 disabled:opacity-50 transition"
        >
          <span>Extract Vertical Slice & Proceed</span>
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>

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
              placeholder="Filter entrypoints or FQN..."
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

          {/* Layer Filter Tabs */}
          <div className="flex items-center p-0.5 bg-slate-950 rounded-lg border border-slate-800 text-[10px] font-mono">
            {[
              { id: 'ALL', label: 'All' },
              { id: 'Presentation', label: 'UI' },
              { id: 'API', label: 'API' },
              { id: 'Integration', label: 'Gateway' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveLayerTab(tab.id as any)}
                className={`flex-1 py-1 rounded text-center transition ${
                  activeLayerTab === tab.id
                    ? 'bg-sky-600 text-white font-bold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Entrypoint List */}
          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {filteredEntrypoints.length > 0 ? (
              filteredEntrypoints.map((entry) => {
                const isSelected = selectedEntrypoint?.fqn === entry.fqn;
                return (
                  <button
                    key={entry.fqn}
                    onClick={() => handleSelectEntrypoint(entry)}
                    className={`w-full p-2.5 rounded-lg border text-left transition flex flex-col gap-1 ${
                      isSelected
                        ? 'bg-sky-950/70 border-sky-500 text-sky-200 ring-1 ring-sky-500/50'
                        : 'bg-slate-950/80 border-slate-800 text-slate-300 hover:bg-slate-800/40 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-mono text-xs font-bold truncate">
                        {entry.simple_name}
                      </span>
                      <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 shrink-0">
                        {entry.layer}
                      </span>
                    </div>

                    <span className="text-[10px] text-slate-500 font-mono truncate">
                      {entry.fqn}
                    </span>

                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {entry.annotations.map((ann) => (
                        <span
                          key={ann}
                          className="text-[9px] font-mono px-1 py-0.2 rounded bg-slate-900 border border-slate-700/60 text-amber-300"
                        >
                          @{ann.replace(/^@/, '')}
                        </span>
                      ))}
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

        {/* Column 2: Topology Canvas */}
        <div className="col-span-12 lg:col-span-6 flex flex-col gap-2 bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-sm">
          {/* Breadcrumb Header */}
          <div className="flex items-center justify-between px-2 py-1 border-b border-slate-800/80 text-xs font-mono">
            <div className="flex items-center gap-1.5 text-slate-400 truncate">
              <GitCommit className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
              <span>Root:</span>
              <strong className="text-sky-300 font-bold truncate">
                {selectedEntrypoint?.simple_name || 'Select Entry Point'}
              </strong>
              <ChevronRight className="h-3 w-3 text-slate-600 shrink-0" />
              <span>{sliceDepth} Hops</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[11px] text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                {sliceData?.nodes.length || 0} Nodes / {sliceData?.edges.length || 0} Edges
              </span>
            </div>
          </div>

          {/* Cytoscape Canvas */}
          <div className="flex-1 w-full h-full relative rounded-lg overflow-hidden border border-slate-800/80 min-h-[460px]">
            <CytoscapeGraph
              nodes={sliceData?.nodes || []}
              edges={sliceData?.edges || []}
              selectedNodeId={selectedNode?.id}
              onSelectNode={setSelectedNode}
            />
          </div>
        </div>

        {/* Column 3: Slice Bounding & Node Inspector */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-4 bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm overflow-y-auto max-h-[720px]">
          {/* Traversal Depth Slider */}
          <div className="flex flex-col gap-2 pb-3 border-b border-slate-800">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white font-mono flex items-center gap-1.5">
                <Sliders className="h-3.5 w-3.5 text-sky-400" />
                Traversal Depth: {sliceDepth} Hops
              </span>
              <span className="text-[10px] text-slate-500 font-mono">1 to 8 hops</span>
            </div>
            <input
              type="range"
              min="1"
              max="8"
              value={sliceDepth}
              onChange={(e) => handleDepthChange(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-950 rounded-lg appearance-none cursor-pointer accent-sky-500"
            />
          </div>

          {/* Token Burn Meter (Guardrail Budget: ≤ 6,000 tokens) */}
          <div className="flex flex-col gap-2 p-3 bg-slate-950 rounded-lg border border-slate-800">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5 font-mono">
                <Gauge className="h-3.5 w-3.5 text-sky-400" />
                LLM Context Budget
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
              <div className="mt-1 p-2 rounded bg-rose-950/80 border border-rose-800 text-[10px] text-rose-300 flex items-start gap-1.5">
                <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" />
                <span>
                  Slice exceeds 6,000 tokens. Reduce traversal depth hops to prevent LLM context overflow.
                </span>
              </div>
            )}
          </div>

          {/* Selected Node Inspector */}
          <div className="flex flex-col gap-2 flex-1">
            <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-1.5">
              <Info className="h-3.5 w-3.5 text-sky-400" />
              Component Inspector
            </span>

            {selectedNode ? (
              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs font-mono flex flex-col gap-2.5">
                <div>
                  <span className="text-slate-500 text-[10px] block">Class Name:</span>
                  <span className="font-bold text-white text-sm">{selectedNode.name || selectedNode.label}</span>
                </div>

                <div>
                  <span className="text-slate-500 text-[10px] block">Fully Qualified Name:</span>
                  <span className="text-sky-300 break-all text-[11px]">{selectedNode.fqn}</span>
                </div>

                {selectedNode.file_path && (
                  <div>
                    <span className="text-slate-500 text-[10px] block">File Location:</span>
                    <span className="text-slate-300 text-[11px] truncate block" title={selectedNode.file_path}>
                      {selectedNode.file_path}
                    </span>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-slate-500 text-[10px] block">Architectural Role:</span>
                    <span className="text-slate-200 font-semibold">{selectedNode.role}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] block">Layer:</span>
                    <span className="text-slate-200">{selectedNode.layer}</span>
                  </div>
                </div>

                {selectedNode.annotations && selectedNode.annotations.length > 0 && (
                  <div>
                    <span className="text-slate-500 text-[10px] block">Annotations:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {selectedNode.annotations.map((a) => (
                        <span
                          key={a}
                          className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-amber-300 text-[10px]"
                        >
                          @{a.replace(/^@/, '')}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {selectedNode.methods && selectedNode.methods.length > 0 && (
                  <div>
                    <span className="text-slate-500 text-[10px] block">Declared Methods:</span>
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
              disabled={!sliceData || isExtracting || isOverBudget || !selectedEntrypoint}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg font-semibold text-xs text-white bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-600 hover:to-indigo-700 shadow-md shadow-sky-500/20 disabled:opacity-50 transition"
            >
              <span>Extract Vertical Slice & Proceed</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
