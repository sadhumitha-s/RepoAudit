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
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Score History</h2>
        {categoryNames.length > 0 && (
          <button
            onClick={() => setShowCategories(!showCategories)}
            className="rounded-md border border-[var(--border)] px-3 py-1 text-xs text-[var(--muted)] transition-colors hover:bg-gray-50"
          >
            {showCategories ? "Hide" : "Show"} Categories
          </button>
        )}
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12 }}
            stroke="var(--muted)"
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 12 }}
            stroke="var(--muted)"
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const data = payload[0].payload as Record<string, string | number>;
              return (
                <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm shadow-lg">
                  <p className="font-mono text-xs text-[var(--muted)]">
                    {data.commit}
                  </p>
                  <p className="font-semibold">Score: {data.score}</p>
                  {showCategories &&
                    categoryNames.map((name) => (
                      <p key={name} className="text-xs">
                        <span
                          className="mr-1 inline-block h-2 w-2 rounded-full"
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
            type="monotone"
            dataKey="score"
            name="Total Score"
            stroke="var(--primary)"
            strokeWidth={2}
            dot={{ r: 4 }}
            activeDot={{ r: 6 }}
          />
          {showCategories &&
            categoryNames.map((name) => (
              <Line
                key={name}
                type="monotone"
                dataKey={name}
                name={name.charAt(0).toUpperCase() + name.slice(1)}
                stroke={CATEGORY_COLORS[name] || "#94a3b8"}
                strokeWidth={1.5}
                strokeDasharray="4 2"
                dot={false}
              />
            ))}
        </LineChart>
      </ResponsiveContainer>

      <p className="mt-2 text-center text-xs text-[var(--muted)]">
        {points.length} audit{points.length !== 1 ? "s" : ""} tracked
      </p>
    </div>
  );
}