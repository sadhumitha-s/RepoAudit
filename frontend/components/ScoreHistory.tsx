"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { getScoreHistory, type ScoreHistoryPoint } from "@/lib/api";

interface Props {
  owner: string;
  repo: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  environment: "#8b5cf6",
  determinism: "#3b82f6",
  datasets: "#10b981",
  semantic: "#f59e0b",
  execution: "#ef4444",
  documentation: "#6366f1",
};

export function ScoreHistory({ owner, repo }: Props) {
  const [points, setPoints] = useState<ScoreHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCategories, setShowCategories] = useState(false);

  useEffect(() => {
    getScoreHistory(owner, repo)
      .then((res) => setPoints(res.points))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [owner, repo]);

  if (loading) {
    return (
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
        <div className="h-48 animate-pulse rounded bg-gray-100" />
      </div>
    );
  }

  if (points.length < 2) return null;

  const categoryNames = points[0]?.categories.map((c) => c.name) ?? [];

  const chartData = points.map((p) => {
    const entry: Record<string, string | number> = {
      date: new Date(p.created_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      }),
      commit: p.commit_hash.slice(0, 7),
      score: Math.round(p.score),
    };
    for (const cat of p.categories) {
      entry[cat.name] = Math.round(cat.score);
    }
    return entry;
  });

  return (
    <div className="neo-card p-6 flex flex-col">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h2 className="text-xl font-bold uppercase tracking-wide text-white">Score History</h2>
        {categoryNames.length > 0 && (
          <button
            onClick={() => setShowCategories(!showCategories)}
            className="neo-button px-4 py-2 text-xs bg-white text-black"
          >
            {showCategories ? "HIDE" : "SHOW"} CATEGORIES
          </button>
        )}
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="0" stroke="#3f3f46" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 13, fill: "#e0e0e0", fontWeight: 'bold' }}
            stroke="#3f3f46"
            strokeWidth={2}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 13, fill: "#e0e0e0", fontWeight: 'bold' }}
            stroke="#3f3f46"
            strokeWidth={2}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const data = payload[0].payload as Record<string, string | number>;
              return (
                <div className="border-2 border-black bg-brand-accent p-4 shadow-neo text-black font-bold">
                  <p className="font-mono text-sm border-b-2 border-black pb-2 mb-2 uppercase">
                    COMMIT: {data.commit}
                  </p>
                  <p className="text-lg mb-2 text-black">TOTAL: {data.score}</p>
                  {showCategories &&
                    categoryNames.map((name) => (
                      <p key={name} className="text-sm uppercase flex items-center gap-2">
                        <span
                          className="inline-block h-3 w-3 border border-black"
                          style={{
                            backgroundColor:
                              CATEGORY_COLORS[name] || "#94a3b8",
                          }}
                        />
                        {name}: {data[name]}
                      </p>
                    ))}
                </div>
              );
            }}
          />
          <Line
            type="linear"
            dataKey="score"
            name="Total Score"
            stroke="#E6D18C"
            strokeWidth={4}
            dot={{ r: 6, strokeWidth: 2, fill: "#000", stroke: "#E6D18C" }}
            activeDot={{ r: 8, strokeWidth: 2, fill: "#E6D18C", stroke: "#000" }}
          />
          {showCategories &&
            categoryNames.map((name) => (
              <Line
                key={name}
                type="linear"
                dataKey={name}
                name={name.charAt(0).toUpperCase() + name.slice(1)}
                stroke={CATEGORY_COLORS[name] || "#94a3b8"}
                strokeWidth={2}
                strokeDasharray="0"
                dot={{ r: 4, strokeWidth: 2, fill: "#000", stroke: CATEGORY_COLORS[name] || "#94a3b8" }}
              />
            ))}
        </LineChart>
      </ResponsiveContainer>

      <p className="mt-6 text-center text-sm font-bold uppercase tracking-widest text-gray-500 border-t-2 border-[#3f3f46] pt-4">
        {points.length} AUDIT{points.length !== 1 ? "S" : ""} TRACKED
      </p>
    </div>
  );
}