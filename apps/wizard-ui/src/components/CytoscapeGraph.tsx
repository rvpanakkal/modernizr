import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { GraphNode, GraphEdge } from '../store/wizardStore';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';

// Register dagre layout plugin once
try {
  cytoscape.use(dagre);
} catch (e) {
  // plugin may already be registered
}

interface CytoscapeGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId?: string;
  onSelectNode: (node: GraphNode | null) => void;
}

export const CytoscapeGraph: React.FC<CytoscapeGraphProps> = ({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Transform store nodes/edges into Cytoscape element definitions
    const cyElements = [
      ...nodes.map((node) => ({
        data: {
          id: node.id,
          label: node.name,
          color: node.color || '#3b82f6',
          role: node.role,
          layer: node.layer,
          fqn: node.fqn,
          raw: node,
        },
      })),
      ...edges.map((edge) => ({
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.label || edge.type,
          type: edge.type,
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements: cyElements,
      boxSelectionEnabled: false,
      autounselectify: false,
      layout: {
        name: 'dagre',
        rankDir: 'TB',
        nodeSep: 60,
        rankSep: 80,
        padding: 40,
      } as any,
      style: [
        {
          selector: 'node',
          style: {
            'shape': 'round-rectangle',
            'background-color': 'data(color)',
            'label': 'data(label)',
            'color': '#ffffff',
            'font-family': "'JetBrains Mono', Consolas, monospace",
            'font-size': '12px',
            'font-weight': 600,
            'text-valign': 'center',
            'text-halign': 'center',
            'width': 'label',
            'height': 42,
            'padding': '14px',
            'border-width': 2,
            'border-color': 'rgba(255, 255, 255, 0.25)',
            'border-opacity': 0.8,
            'text-outline-color': '#0f172a',
            'text-outline-width': 2,
            'transition-property': 'border-color, border-width, background-color',
            'transition-duration': 0.2,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#38bdf8',
            'shadow-blur': 25,
            'shadow-color': '#38bdf8',
            'shadow-opacity': 0.6,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 2.5,
            'line-color': '#475569',
            'target-arrow-color': '#94a3b8',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 1.2,
            'label': 'data(label)',
            'font-size': '10px',
            'font-family': "'JetBrains Mono', Consolas, monospace",
            'color': '#94a3b8',
            'text-background-color': '#0f172a',
            'text-background-opacity': 0.85,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
          },
        },
        {
          selector: 'edge[type = "INJECTS"]',
          style: {
            'line-style': 'dashed',
            'line-color': '#38bdf8',
            'target-arrow-color': '#38bdf8',
          },
        },
        {
          selector: 'edge[type = "CALLS"]',
          style: {
            'line-color': '#10b981',
            'target-arrow-color': '#10b981',
          },
        },
      ] as any,
    });

    cy.on('tap', 'node', (evt) => {
      const nodeData = evt.target.data('raw');
      onSelectNode(nodeData || null);
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        onSelectNode(null);
      }
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [nodes, edges]);

  // Sync selectedNodeId with Cytoscape selection
  useEffect(() => {
    if (!cyRef.current) return;
    const cy = cyRef.current;
    cy.nodes().unselect();
    if (selectedNodeId) {
      cy.nodes(`[id = "${selectedNodeId}"]`).select();
    }
  }, [selectedNodeId]);

  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleFit = () => cyRef.current?.fit(undefined, 30);

  return (
    <div className="relative w-full h-full min-h-[460px] bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-inner">
      {/* Canvas container for Cytoscape */}
      <div ref={containerRef} className="w-full h-full" />

      {/* Graph Control Overlay */}
      <div className="absolute top-4 right-4 flex items-center gap-1.5 p-1 bg-slate-900/90 backdrop-blur border border-slate-700/80 rounded-lg shadow-lg">
        <button
          onClick={handleZoomIn}
          title="Zoom In"
          className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          onClick={handleZoomOut}
          title="Zoom Out"
          className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          onClick={handleFit}
          title="Fit View"
          className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>

      {/* Legend Overlay */}
      <div className="absolute bottom-4 left-4 p-2.5 bg-slate-900/90 backdrop-blur border border-slate-800 rounded-lg shadow-md text-[11px] font-mono flex flex-wrap gap-3">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm bg-[#3b82f6]" />
          <span className="text-slate-300">Presentation</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm bg-[#10b981]" />
          <span className="text-slate-300">Domain Service</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm bg-[#8b5cf6]" />
          <span className="text-slate-300">Gateway / CICS</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm bg-[#f59e0b]" />
          <span className="text-slate-300">Data Access</span>
        </div>
      </div>
    </div>
  );
};
