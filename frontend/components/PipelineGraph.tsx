"use client";

import React, { useMemo } from 'react';
import ReactFlow, { 
  Background, 
  Controls, 
  Edge, 
  Node, 
  MarkerType,
  Handle,
  Position
} from 'reactflow';
import 'reactflow/dist/style.css';

interface PipelineNodeData {
  label: string;
  stage: string;
  file?: string;
  status: string;
  framework?: string;
}

const STAGE_COLORS: Record<string, string> = {
  dataset: '#3b82f6', // blue
  preprocessing: '#8b5cf6', // purple
  feature_engineering: '#ec4899', // pink
  training: '#f59e0b', // amber
  evaluation: '#10b981', // emerald
  inference: '#06b6d4', // cyan
  artifact: '#64748b', // slate
};

const CustomNode = ({ data }: { data: PipelineNodeData }) => {
  const color = STAGE_COLORS[data.stage] || '#94a3b8';
  
  return (
    <div className="neo-card p-3 min-w-[180px] border-l-4" style={{ borderLeftColor: color }}>
      <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-zinc-600" />
      <div className="flex flex-col space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-zinc-500">
            {data.stage}
          </span>
          {data.framework && (
            <span className="text-[10px] bg-zinc-800 px-1 rounded text-zinc-400 font-mono">
              {data.framework}
            </span>
          )}
        </div>
        <div className="text-sm font-bold text-white truncate">
          {data.label}
        </div>
        {data.file && (
          <div className="text-[10px] text-zinc-500 font-mono truncate">
            {data.file}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-zinc-600" />
    </div>
  );
};

const nodeTypes = {
  pipeline: CustomNode,
};

interface Props {
  graph?: {
    nodes: any[];
    edges: any[];
    completeness_score: number;
  };
}

export function PipelineGraph({ graph }: Props) {
  const nodes: Node[] = useMemo(() => {
    return (graph?.nodes ?? []).map((n, i) => ({
      id: n.id,
      type: 'pipeline',
      data: { 
        label: n.label, 
        stage: n.stage, 
        file: n.file, 
        status: n.status,
        framework: n.framework 
      },
      // Simple vertical layout for now
      position: { x: 0, y: i * 120 },
    }));
  }, [graph?.nodes]);

  const edges: Edge[] = useMemo(() => {
    return (graph?.edges ?? []).map((e, i) => ({
      id: `e-${i}`,
      source: e.source,
      target: e.target,
      animated: e.type === 'data_flow',
      style: { stroke: '#52525b', strokeWidth: 2 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: '#52525b',
      },
    }));
  }, [graph?.edges]);

  return (
    <div className="neo-card p-0 h-[500px] relative overflow-hidden bg-black/40">
      <div className="absolute top-4 left-4 z-10 flex items-center gap-3">
        <h3 className="text-sm font-black uppercase tracking-tighter text-white">Pipeline Reconstruction</h3>
        <div className="flex items-center gap-2 bg-zinc-900/80 px-2 py-1 rounded border border-zinc-800 shadow-xl">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] font-bold text-zinc-400">
            Completeness: {Math.round(graph?.completeness_score ?? 0)}%
          </span>
        </div>
      </div>
      
      {nodes.length > 0 ? (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          className="bg-dot-pattern"
        >
          <Background color="#18181b" gap={20} />
          <Controls showInteractive={false} className="!bg-zinc-900 !border-zinc-800 !fill-white shadow-neo" />
        </ReactFlow>
      ) : (
        <div className="flex flex-col items-center justify-center h-full space-y-4">
          <div className="w-12 h-12 rounded-full border-2 border-dashed border-zinc-700 flex items-center justify-center">
            <span className="text-zinc-600 text-xl font-black">?</span>
          </div>
          <div className="text-center px-6">
            <p className="text-zinc-400 font-bold uppercase text-xs tracking-widest">No ML stages detected</p>
            <p className="text-zinc-600 text-[10px] max-w-[280px] mt-2 italic leading-relaxed">
              We couldn't reconstruct the pipeline graph. This happens if the repo uses custom frameworks or lacks standard training signals (e.g. Scikit-learn fit, PyTorch train loops).
            </p>
          </div>
        </div>
      )}

      <style jsx global>{`
        .bg-dot-pattern {
          background-image: radial-gradient(#27272a 1px, transparent 0);
          background-size: 20px 20px;
        }
        .react-flow__handle {
          border: 1px solid #3f3f46;
        }
        .react-flow__controls button {
          background-color: #18181b;
          border-bottom: 2px solid #27272a;
          color: white;
        }
        .react-flow__controls button:hover {
          background-color: #27272a;
        }
        .react-flow__attribution {
          display: none;
        }
      `}</style>
    </div>
  );
}
