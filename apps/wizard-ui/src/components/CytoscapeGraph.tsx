import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { GraphNode, GraphEdge, LayerType } from '../types/graph';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';

// Register dagre layout plugin once
try {
  cytoscape.use(dagre);
} catch (e) {
  // plugin already registered
}

const LAYER_COLORS: Record<LayerType | string, string> = {
  PRESENTATION: '#3b82f6', // Blue
  API: '#06b6d4',          // Cyan
  SERVICE: '#10b981',      // Emerald
  INTEGRATION: '#8b5cf6',  // Purple
  DATA: '#f59e0b',         // Amber
  UTIL: '#6b7280',         // Slate/Gray
};

interface CytoscapeGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId?: string;
  onNodeSelect?: (node: GraphNode | null) => void;
  onSelectNode?: (node: GraphNode | null) => void;
}

export const CytoscapeGraph: React.FC<CytoscapeGraphProps> = ({
  nodes,
  edges,
  selectedNodeId,
  onNodeSelect,
  onSelectNode,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  const handleSelect = (node: GraphNode | null) => {
    if (onNodeSelect) onNodeSelect(node);
    if (onSelectNode) onSelectNode(node);
  };

  useEffect(() => {
    if (!containerRef.current) return;

    // Transform GraphNode & GraphEdge into Cytoscape elements
    const cyElements: cytoscape.ElementDefinition[] = [
      ...nodes.map((node) => {
        const layerKey = (node.layer || 'SERVICE').toUpperCase() as LayerType;
        const color = LAYER_COLORS[layerKey] || '#3b82f6';
        return {
          data: {
            id: node.id,
            label: node.label || node.name || node.id.split('.').pop() || 'Node',
            layer: layerKey,
            color,
            raw: node,
          },
        };
      }),
      ...edges.map((edge) => {
        const rel = edge.relationship || edge.type || 'CALLS';
        return {
          data: {
            id: edge.id || `${edge.source}->${edge.target}`,
            source: edge.source,
            target: edge.target,
            relationship: rel,
            label: edge.label || rel,
          },
        };
      }),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements: cyElements,
      boxSelectionEnabled: false,
      autounselectify: false,
      wheelSensitivity: 0.3,
      layout: {
        name: 'dagre',
        rankDir: 'TB',
        nodeSep: 60,
        rankSep: 85,
        padding: 40,
        animate: false,
      } as any,
      style: [
        {
          selector: 'node',
          style: {
            'shape': 'round-rectangle',
            'background-color': '#0f172a',
            'border-width': 2.5,
            'border-color': 'data(color)',
            'label': 'data(label)',
            'color': '#f8fafc',
            'font-family': "'JetBrains Mono', Consolas, monospace",
            'font-size': '11px',
            'font-weight': 600,
            'text-valign': 'center',
            'text-halign': 'center',
            'width': 'label',
            'height': 38,
            'padding': '14px',
            'transition-property': 'border-color, border-width, shadow-blur, shadow-color',
            'transition-duration': 0.2,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#38bdf8',
            'shadow-blur': 24,
            'shadow-color': '#38bdf8',
            'shadow-opacity': 0.8,
            'background-color': '#1e293b',
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#475569',
            'target-arrow-color': '#94a3b8',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 1.1,
            'label': 'data(label)',
            'font-size': '9px',
            'font-family': "'JetBrains Mono', Consolas, monospace",
            'color': '#94a3b8',
            'text-background-color': '#020617',
            'text-background-opacity': 0.85,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
          },
        },
        {
          selector: 'edge[relationship = "INJECTS"]',
          style: {
            'line-style': 'dashed',
            'line-color': '#38bdf8',
            'target-arrow-color': '#38bdf8',
          },
        },
        {
          selector: 'edge[relationship = "CALLS"]',
          style: {
            'line-style': 'solid',
            'line-color': '#10b981',
            'target-arrow-color': '#10b981',
          },
        },
        {
          selector: 'edge[relationship = "USES"]',
          style: {
            'line-style': 'dotted',
            'line-color': '#8b5cf6',
            'target-arrow-color': '#8b5cf6',
          },
        },
        {
          selector: 'edge[relationship = "EXTENDS"]',
          style: {
            'line-style': 'solid',
            'line-color': '#f59e0b',
            'target-arrow-color': '#f59e0b',
          },
        },
      ] as any,
    });

    cy.on('tap', 'node', (evt) => {
      const raw = evt.target.data('raw');
      handleSelect(raw || null);
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        handleSelect(null);
      }
    });

    // Auto-fit with padding
    if (nodes.length > 0) {
      cy.fit(undefined, 30);
    }

    cyRef.current = cy;

    const handleResize = () => {
      if (cyRef.current) {
        cyRef.current.resize();
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cy.destroy();
      cyRef.current = null;
    };
  }, [nodes, edges]);

  // Synchronize external selectedNodeId with Cytoscape selection
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
      {/* Cytoscape Container */}
      <div ref={containerRef} className="w-full h-full min-h-[460px]" />

      {/* Floating HUD Controls */}
      <div className="absolute top-3 right-3 flex items-center gap-1 p-1 bg-slate-900/90 backdrop-blur border border-slate-700/80 rounded-lg shadow-lg z-10">
        <button
          onClick={handleZoomIn}
          title="Zoom In"
          aria-label="Zoom In"
          className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          onClick={handleZoomOut}
          title="Zoom Out"
          aria-label="Zoom Out"
          className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          onClick={handleFit}
          title="Fit Canvas"
          aria-label="Fit Canvas"
          className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>

      {/* Legend Overlay */}
      <div className="absolute bottom-3 left-3 p-2 bg-slate-900/90 backdrop-blur border border-slate-800 rounded-lg shadow-md text-[10px] font-mono flex flex-wrap items-center gap-3 z-10">
        {(Object.entries(LAYER_COLORS) as [LayerType, string][]).map(([layer, color]) => (
          <div key={layer} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: color }} />
            <span className="text-slate-300">{layer}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
