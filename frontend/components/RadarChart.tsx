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
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold">Category Breakdown</h2>
      <ResponsiveContainer width="100%" height={280}>
        <RechartsRadarChart data={data}>
          <PolarGrid stroke="var(--border)" />
          <PolarAngleAxis
            dataKey="category"
            tick={{ fontSize: 12, fill: "var(--muted)" }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: "var(--muted)" }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "8px",
              fontSize: "13px",
            }}
            formatter={(value: number) => [`${value}/100`, "Score"]}
          />
          <Radar
            name="Score"
            dataKey="score"
            stroke="#0284c7"
            fill="#0ea5e9"
            fillOpacity={0.25}
            strokeWidth={2}
          />
        </RechartsRadarChart>
      </ResponsiveContainer>
    </div>
  );
}