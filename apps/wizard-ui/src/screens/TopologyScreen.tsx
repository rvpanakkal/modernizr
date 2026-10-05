import React, { useEffect, useState } from 'react';
import { useWizardStore, EntrypointItem, GraphNode } from '../store/wizardStore';
import { apiClient } from '../services/api';
import { CytoscapeGraph } from '../components/CytoscapeGraph';
import {
  Layers,
  ArrowRight,
  Sliders,
  Gauge,
  CheckCircle,
  AlertTriangle,
  Info,
  Code2,
  GitCommit,
  Sparkles,
} from 'lucide-react';

export const TopologyScreen: React.FC = () => {
  const {
    entrypoints,
    setEntrypoints,
    selectedEntrypoint,
    selectEntrypoint,
    sliceDepth,
    setSliceDepth,
    sliceData,
    setSliceData,
    selectedNode,
    setSelectedNode,
    setRunId,
    setStep,
    resetTelemetry,
  } = useWizardStore();

  const [isLoading, setIsLoading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);

  // Fetch entry points on initial load if not loaded
  useEffect(() => {
    const loadEntrypoints = async () => {
      if (entrypoints.length === 0) {
        setIsLoading(true);
        try {
          const list = await apiClient.getEntrypoints();
          setEntrypoints(list);
          if (list.length > 0) {
            loadSlice(list[0].fqn, sliceDepth);
          }
        } catch (err) {
          console.error('Failed to load entrypoints:', err);
        } finally {
          setIsLoading(false);
        }
      } else if (!sliceData && selectedEntrypoint) {
        loadSlice(selectedEntrypoint.fqn, sliceDepth);
      }
    };
    loadEntrypoints();
  }, []);

  const loadSlice = async (entryFqn: string, depth: number) => {
    setIsLoading(true);
    try {
      const data = await apiClient.getVerticalSlice(entryFqn, depth);
      setSliceData(data);
    } catch (err) {
      console.error('Failed to extract slice:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectEntrypoint = (entry: EntrypointItem) => {
    selectEntrypoint(entry);
    loadSlice(entry.fqn, sliceDepth);
  };

  const handleDepthChange = (newDepth: number) => {
    setSliceDepth(newDepth);
    if (selectedEntrypoint) {
      loadSlice(selectedEntrypoint.fqn, newDepth);
    }
  };

  const handleProceedToChain = async () => {
    if (!selectedEntrypoint || !sliceData) return;
    setIsExtracting(true);
    resetTelemetry();

    try {
      const runResp = await apiClient.startPipelineRun(
        selectedEntrypoint.fqn,
        sliceData.raw_slice,
        'jira'
      );
      setRunId(runResp.run_id);
      // Advance to Step 3 (Telemetry console)
      setStep(3);
    } catch (err) {
      console.error('Failed to start pipeline run:', err);
    } finally {
      setIsExtracting(false);
    }
  };

  // Group entrypoints by layer
  const groupedEntries: Record<string, EntrypointItem[]> = {
    Presentation: entrypoints.filter((e) => e.layer === 'Presentation'),
    API: entrypoints.filter((e) => e.layer === 'API'),
    Integration: entrypoints.filter((e) => e.layer === 'Integration'),
  };

  const estimatedTokens = sliceData?.estimated_tokens || 1450;
  const maxTokens = 6000;
  const tokenPercentage = Math.min(Math.round((estimatedTokens / maxTokens) * 100), 100);

  return (
    <div className="flex flex-col gap-4 flex-1 h-full w-full">
      {/* Header Bar */}
      <div className="flex items-center justify-between">
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
            Identify presentation entry-points, traverse INJECTS & CALLS edges in Neo4j, and bound vertical execution slices under 6,000 tokens.
          </p>
        </div>

        <button
          onClick={handleProceedToChain}
          disabled={!sliceData || isExtracting}
          className="flex items-center gap-2 py-2 px-4 rounded-xl font-semibold text-xs text-white bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-600 hover:to-indigo-700 shadow-md shadow-sky-500/20 disabled:opacity-50 transition"
        >
          <span>Extract Vertical Slice & Proceed</span>
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>

      {/* Main 3-Column Interactive Layout */}
      <div className="grid grid-cols-12 gap-4 flex-1 min-h-[560px]">
        {/* Left Sidebar: Discovered Entry Points */}
        <div className="col-span-12 lg:col-span-3 bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col gap-4 shadow-sm overflow-y-auto max-h-[640px]">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5 text-sky-400" />
              Discovered Entrypoints ({entrypoints.length})
            </span>
          </div>

          <div className="flex flex-col gap-4">
            {Object.entries(groupedEntries).map(([layer, items]) => {
              if (items.length === 0) return null;
              return (
                <div key={layer} className="flex flex-col gap-2">
                  <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500 font-bold px-1">
                    {layer} Layer
                  </span>
                  <div className="flex flex-col gap-1.5">
                    {items.map((entry) => {
                      const isSelected = selectedEntrypoint?.fqn === entry.fqn;
                      return (
                        <button
                          key={entry.fqn}
                          onClick={() => handleSelectEntrypoint(entry)}
                          className={`p-2.5 rounded-lg border text-left transition flex flex-col gap-1 ${
                            isSelected
                              ? 'bg-sky-950/60 border-sky-500 text-sky-200 ring-1 ring-sky-500/40'
                              : 'bg-slate-950 border-slate-800 text-slate-300 hover:bg-slate-800/40'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-mono text-xs font-bold truncate">
                              {entry.simple_name}
                            </span>
                            <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400">
                              {entry.role}
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono truncate">
                            {entry.fqn}
                          </span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {entry.annotations.map((ann) => (
                              <span
                                key={ann}
                                className="text-[9px] font-mono px-1 py-0.2 rounded bg-slate-900 border border-slate-700/60 text-slate-400"
                              >
                                @{ann}
                              </span>
                            ))}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Center Canvas: Cytoscape Graph */}
        <div className="col-span-12 lg:col-span-6 flex flex-col gap-2 bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-sm min-h-[460px]">
          <div className="flex items-center justify-between px-2 py-1">
            <div className="flex items-center gap-2">
              <GitCommit className="h-4 w-4 text-emerald-400" />
              <span className="text-xs font-bold text-white font-mono">
                Directed Call Graph Topology
              </span>
            </div>
            {selectedEntrypoint && (
              <span className="text-[11px] font-mono text-slate-400">
                Root: <strong className="text-sky-300">{selectedEntrypoint.simple_name}</strong>
              </span>
            )}
          </div>

          <div className="flex-1 w-full h-full relative rounded-lg overflow-hidden border border-slate-800/80">
            <CytoscapeGraph
              nodes={sliceData?.nodes || []}
              edges={sliceData?.edges || []}
              selectedNodeId={selectedNode?.id}
              onSelectNode={setSelectedNode}
            />
          </div>
        </div>

        {/* Right Column: Controls, Token Budget & Node Inspector */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-4 bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm overflow-y-auto max-h-[640px]">
          {/* Depth Slider */}
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

          {/* Token Meter (Invariant: ≤ 6,000 tokens) */}
          <div className="flex flex-col gap-2 p-3 bg-slate-950 rounded-lg border border-slate-800">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5 font-mono">
                <Gauge className="h-3.5 w-3.5 text-sky-400" />
                LLM Context Slice
              </span>
              <span className="text-xs font-mono font-bold text-emerald-400">
                {estimatedTokens.toLocaleString()} / {maxTokens.toLocaleString()}
              </span>
            </div>

            <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${
                  tokenPercentage < 70
                    ? 'bg-emerald-500'
                    : tokenPercentage < 90
                    ? 'bg-amber-500'
                    : 'bg-rose-500'
                }`}
                style={{ width: `${tokenPercentage}%` }}
              />
            </div>

            <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
              <span>{tokenPercentage}% of budget</span>
              <span className="text-emerald-400 flex items-center gap-1">
                <CheckCircle className="h-2.5 w-2.5" />
                Within Guardrail Budget
              </span>
            </div>
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
                  <span className="text-slate-500 text-[10px] block">Name:</span>
                  <span className="font-bold text-white text-sm">{selectedNode.name}</span>
                </div>

                <div>
                  <span className="text-slate-500 text-[10px] block">Fully Qualified Name:</span>
                  <span className="text-sky-300 break-all text-[11px]">{selectedNode.fqn}</span>
                </div>

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

                <div>
                  <span className="text-slate-500 text-[10px] block">Annotations:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {selectedNode.annotations.map((a) => (
                      <span
                        key={a}
                        className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300 text-[10px]"
                      >
                        @{a}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <span className="text-slate-500 text-[10px] block">Declared Methods:</span>
                  <div className="flex flex-col gap-0.5 mt-1 text-[11px] text-slate-300">
                    {selectedNode.methods.map((m) => (
                      <div key={m} className="truncate">
                        • {m}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-4 bg-slate-950 rounded-lg border border-slate-800/80 text-center text-slate-500 text-xs py-10">
                Click any node in the topology canvas to inspect methods, annotations, and parameters.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
