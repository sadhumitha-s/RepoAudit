import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { DecayMetrics } from "@/lib/api";

interface Props {
  metrics: DecayMetrics;
}

export function DecayCard({ metrics }: Props) {
  const shelfLifeYears = (metrics.shelf_life_days / 365).toFixed(1);
  const breakYears = (metrics.time_to_break_days / 365).toFixed(1);

  return (
    <div className="border-2 border-white bg-black p-6 shadow-neo transform transition-transform hover:-translate-y-1 hover:shadow-[8px_8px_0_0_#fff]">
      <h2 className="text-xl font-black uppercase tracking-wide text-white mb-6 border-b-2 border-white pb-2">
        Reproducibility Decay
      </h2>
      
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div>
          <div className="text-[#a1a1aa] text-xs font-bold uppercase mb-1">Estimated Shelf Life</div>
          <div className="text-3xl font-black text-brand-accent">{shelfLifeYears} <span className="text-sm">YRS</span></div>
        </div>
        <div>
          <div className="text-[#a1a1aa] text-xs font-bold uppercase mb-1">Time-to-Break</div>
          <div className="text-3xl font-black text-red-500">{breakYears} <span className="text-sm">YRS</span></div>
        </div>
      </div>

      <div className="h-48 w-full mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={metrics.decay_curve} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="date" stroke="#e5e5e5" tick={{ fill: "#a1a1aa", fontSize: 12 }} />
            <YAxis domain={[0, 100]} stroke="#e5e5e5" tick={{ fill: "#a1a1aa", fontSize: 12 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "#111", border: "2px solid #fff", color: "#fff", fontWeight: "bold" }}
              itemStyle={{ color: "#bef264" }}
            />
            <Line
              type="monotone"
              dataKey="score"
              stroke="#bef264"
              strokeWidth={3}
              activeDot={{ r: 6, fill: "#bef264", stroke: "#fff", strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-[#a1a1aa] mt-4 font-bold uppercase">
        Tracks ecosystem drift based on dependency ages, known CVEs, and yanked packages.
      </p>
    </div>
  );
}
