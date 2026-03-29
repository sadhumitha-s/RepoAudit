"use client";

import {
  Radar,
  RadarChart as RechartsRadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";
import type { AuditResponse } from "@/lib/api";

interface Props {
  results: AuditResponse[];
}

const COLORS = ["#8B5CF6", "#10B981", "#F59E0B", "#EF4444", "#3B82F6"];

const LABEL_MAP: Record<string, string> = {
  environment: "Environment",
  determinism: "Determinism",
  datasets: "Datasets",
  semantic: "Semantic",
  execution: "Execution",
  documentation: "Documentation",
};

export function ComparisonRadarChart({ results }: Props) {
  // Only use completed audits
  const activeReports = results.filter((r) => r.status === "completed" && r.report);

  if (activeReports.length === 0) {
    return (
      <div className="neo-card p-6 flex items-center justify-center h-[400px]">
        <p className="text-zinc-500 font-bold uppercase">Waiting for analysis results...</p>
      </div>
    );
  }

  // Get all unique category names
  const categoryNames = Array.from(
    new Set(
      activeReports.flatMap((r) => r.report?.categories.map((c) => c.name) || [])
    )
  );

  // Prepare data: each object is a category, with values for each repo
  const data = categoryNames.map((catName) => {
    const entry: any = {
      category: LABEL_MAP[catName] || catName,
      fullMark: 100,
    };
    activeReports.forEach((r, idx) => {
      const score = r.report?.categories.find((c) => c.name === catName)?.score || 0;
      entry[`repo_${idx}`] = score;
    });
    return entry;
  });

  return (
    <div className="neo-card p-6 flex flex-col h-[500px]">
      <h2 className="mb-4 text-xl font-bold uppercase tracking-wide text-white">Comparative Reproducibility Radar</h2>
      <ResponsiveContainer width="100%" height="100%">
        <RechartsRadarChart data={data}>
          <PolarGrid stroke="#3f3f46" strokeWidth={2} />
          <PolarAngleAxis
            dataKey="category"
            tick={{ fontSize: 13, fill: "#e0e0e0", fontWeight: 'bold' }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: "#a1a1aa" }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#18181b",
              border: "2px solid #000",
              borderRadius: "0px",
              fontSize: "14px",
              fontWeight: "bold",
              color: "#fff",
              boxShadow: "4px 4px 0px 0px rgba(0,0,0,1)"
            }}
          />
          <Legend 
             wrapperStyle={{ paddingTop: '20px' }}
             formatter={(value) => <span className="text-white font-bold uppercase text-xs">{value}</span>}
          />
          {activeReports.map((r, idx) => {
             // Extract repo name from URL
             const repoName = r.repo_url.split("/").pop() || `Repo ${idx + 1}`;
             return (
               <Radar
                 key={r.audit_id}
                 name={repoName}
                 dataKey={`repo_${idx}`}
                 stroke={COLORS[idx % COLORS.length]}
                 fill={COLORS[idx % COLORS.length]}
                 fillOpacity={0.3}
                 strokeWidth={3}
               />
             );
          })}
        </RechartsRadarChart>
      </ResponsiveContainer>
    </div>
  );
}
