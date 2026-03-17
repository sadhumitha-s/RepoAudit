"use client";

import {
  Radar,
  RadarChart as RechartsRadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { CategoryScore } from "@/lib/api";

interface Props {
  categories: CategoryScore[];
}

const LABEL_MAP: Record<string, string> = {
  environment: "Environment",
  determinism: "Determinism",
  datasets: "Datasets",
  semantic: "Semantic",
  execution: "Execution",
  documentation: "Documentation",
};

export function RadarChart({ categories }: Props) {
  const data = categories.map((c) => ({
    category: LABEL_MAP[c.name] || c.name,
    score: c.score,
    fullMark: 100,
  }));

  return (
    <div className="neo-card p-6 flex flex-col">
      <h2 className="mb-4 text-xl font-bold uppercase tracking-wide text-white">Category Breakdown</h2>
      <ResponsiveContainer width="100%" height={300}>
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
              backgroundColor: "#E6D18C", // Accent color for tooltip
              border: "2px solid #000000",
              borderRadius: "0px",
              fontSize: "14px",
              fontWeight: "bold",
              color: "#000000",
              boxShadow: "4px 4px 0px 0px rgba(0,0,0,1)"
            }}
            itemStyle={{ color: "#000000" }}
            formatter={(value: number) => [`${value}/100`, "SCORE"]}
          />
          <Radar
            name="Score"
            dataKey="score"
            stroke="#E6D18C"
            fill="#E6D18C"
            fillOpacity={0.8}
            strokeWidth={4}
          />
        </RechartsRadarChart>
      </ResponsiveContainer>
    </div>
  );
}