"use client";

import { useState, useEffect } from "react";
import { compareRepositories, getAudit, type AuditResponse } from "@/lib/api";
import { ComparisonRadarChart } from "@/components/ComparisonRadarChart";
import { ScoreCard } from "@/components/ScoreCard";
import { StatusIndicator } from "@/components/StatusIndicator";
import { Trophy, AlertCircle, Plus, X } from "lucide-react";

export default function ComparePage() {
  const [urls, setUrls] = useState<string[]>(["", ""]);
  const [results, setResults] = useState<AuditResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  const handleAddUrl = () => {
    if (urls.length < 5) {
      setUrls([...urls, ""]);
    }
  };

  const handleRemoveUrl = (index: number) => {
    const newUrls = [...urls];
    newUrls.splice(index, 1);
    setUrls(newUrls.length ? newUrls : [""]);
  };

  const handleUrlChange = (index: number, value: string) => {
    const newUrls = [...urls];
    newUrls[index] = value;
    setUrls(newUrls);
  };

  const handleCompare = async () => {
    const filteredUrls = urls.map(u => u.trim()).filter(u => u !== "");
    if (filteredUrls.length < 2) {
       setError("Please enter at least 2 URLs to compare.");
       return;
    }
    setError(null);
    setLoading(true);
    try {
      const resp = await compareRepositories(filteredUrls);
      setResults(resp.results);
      setPolling(true);
    } catch (err: any) {
      setError(err.message || "Failed to start comparison");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let interval: NodeJS.Timeout;
    
    if (polling && results.length > 0) {
      interval = setInterval(async () => {
        const stillProcessing = results.some(r => r.status !== "completed" && r.status !== "failed");
        if (!stillProcessing) {
          setPolling(false);
          return;
        }

        try {
          const updatedResults = await Promise.all(
            results.map(async (r) => {
              if (r.status === "completed" || r.status === "failed") return r;
              try {
                return await getAudit(r.audit_id);
              } catch {
                return r;
              }
            })
          );
          setResults(updatedResults);
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 3000);
    }

    return () => clearInterval(interval);
  }, [polling, results]);

  const winner = [...results]
    .filter(r => r.status === "completed")
    .sort((a, b) => (b.score || 0) - (a.score || 0))[0];

  return (
    <div className="max-w-6xl mx-auto py-10 px-4 space-y-10">
      <div className="text-center space-y-4">
        <h1 className="text-6xl font-black uppercase tracking-tighter text-white italic drop-shadow-[4px_4px_0px_rgba(230,209,140,0.5)]">
           Multi-Repo <span className="text-brand-accent">Combat</span>
        </h1>
        <p className="text-zinc-400 font-bold max-w-2xl mx-auto uppercase text-xs tracking-widest leading-loose">
          Side-by-side reproducibility benchmarking for ML research. <br/>
          Identify the most stable implementation in seconds.
        </p>
      </div>

      <div className="neo-card p-10 bg-brand-card border-4 border-white shadow-neo-white relative overflow-hidden">
        <div className="absolute top-0 right-0 bg-white text-black font-black px-4 py-1 text-[10px] uppercase tracking-tighter">Compare up to 5</div>
        <div className="space-y-6">
           {urls.map((url, idx) => (
             <div key={idx} className="flex gap-3">
                <div className="bg-brand-accent text-black font-black px-4 flex items-center justify-center min-w-[48px] border-2 border-black">
                   {idx + 1}
                </div>
                <input
                  type="text"
                  placeholder="https://github.com/owner/repository-name"
                  className="flex-1 bg-black border-2 border-white p-4 text-white font-mono text-sm focus:outline-none focus:ring-4 focus:ring-brand-accent/30 transition-all placeholder:text-zinc-700"
                  value={url}
                  onChange={(e) => handleUrlChange(idx, e.target.value)}
                />
                {urls.length > 1 && (
                  <button 
                    onClick={() => handleRemoveUrl(idx)}
                    className="p-4 border-2 border-white bg-destructive hover:bg-red-600 transition-colors shadow-neo-sm active:translate-x-0.5 active:translate-y-0.5"
                  >
                    <X size={20} className="text-black font-black" />
                  </button>
                )}
             </div>
           ))}
           {urls.length < 5 && (
             <button 
               onClick={handleAddUrl}
               className="flex items-center gap-2 text-brand-accent hover:text-white font-black uppercase text-[10px] tracking-widest transition-colors p-2"
             >
               <Plus size={14} /> Add Another Repository
             </button>
           )}
        </div>

        <button
          onClick={handleCompare}
          disabled={loading}
          className="mt-10 w-full bg-brand-accent text-black font-black uppercase py-5 text-2xl border-4 border-black hover:translate-x-[4px] hover:translate-y-[4px] hover:shadow-none shadow-neo-lg transition-all active:translate-x-[6px] active:translate-y-[6px] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Warming up Engines..." : "Initialize Combat Analysis"}
        </button>
        {error && (
            <div className="mt-6 p-4 bg-destructive/10 border-2 border-destructive text-destructive font-black flex items-center gap-2 uppercase text-xs tracking-tight">
                <AlertCircle size={18} /> {error}
            </div>
        )}
      </div>

      {results.length > 0 && (
        <div className="space-y-12 animate-in fade-in slide-in-from-bottom-5 duration-1000 pb-32">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
            <div className="lg:col-span-2">
              <ComparisonRadarChart results={results} />
            </div>
            <div className="space-y-6">
               <h3 className="text-2xl font-black uppercase text-white tracking-tighter italic border-b-4 border-brand-accent pb-2">Top Performer</h3>
               {winner ? (
                 <div className="neo-card !bg-brand-accent text-black p-8 border-4 border-black group relative overflow-hidden shadow-neo-lg">
                    <Trophy size={140} className="absolute -right-10 -bottom-10 opacity-30 group-hover:scale-110 transition-transform duration-1000 rotate-12" />
                    <div className="relative z-10">
                        <div className="bg-black text-brand-accent text-[10px] font-black px-2 py-0.5 inline-block mb-3 uppercase tracking-tighter">Golden Standard</div>
                        <h4 className="text-3xl font-black truncate leading-none">{winner.repo_url.split("/").pop()}</h4>
                        <div className="text-8xl font-black mt-2 tracking-tighter leading-none">{Math.round(winner.score || 0)}</div>
                        <p className="text-[11px] font-black uppercase mt-2 opacity-90 tracking-[0.2em]">Reproducibility Score</p>
                    </div>
                 </div>
               ) : (
                 <div className="neo-card bg-zinc-900 p-8 border-4 border-dashed border-zinc-800 flex flex-col items-center justify-center h-[280px] space-y-6">
                    <div className="w-16 h-16 border-8 border-brand-accent border-t-transparent animate-spin rounded-full shadow-neo-sm" />
                    <p className="text-zinc-600 font-black uppercase text-[10px] tracking-[0.3em] text-center max-w-[200px] leading-relaxed">Aggregating Determinism Metrics...</p>
                 </div>
               )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-10">
            {results.map((r, idx) => (
              <div key={idx} className="space-y-4">
                <div className="flex justify-between items-center px-2 border-l-8 border-brand-accent pl-4">
                   <div className="flex flex-col">
                     <span className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Repo {idx + 1}</span>
                     <span className="text-sm font-black text-white uppercase truncate max-w-[200px] tracking-tighter">{r.repo_url.split("/").slice(-2).join("/")}</span>
                   </div>
                   {r.status !== "completed" && r.status !== "failed" && (
                     <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-brand-accent animate-ping rounded-full" />
                        <span className="text-[10px] font-black text-brand-accent uppercase tracking-widest">Live Audit</span>
                     </div>
                   )}
                </div>
                {r.report ? (
                  <div className="hover:-translate-y-2 transition-transform duration-300">
                    <ScoreCard 
                        score={r.report.total_score} 
                        summary={r.report.summary} 
                        commitHash={r.commit_hash}
                        cached={r.cached}
                    />
                  </div>
                ) : (
                  <div className="neo-card p-10 h-[240px] flex items-center justify-center bg-zinc-900/30 border-2 border-white/5 group hover:border-brand-accent/30 transition-all duration-500 overflow-hidden relative">
                     <div className="absolute inset-0 bg-brand-accent/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                     <StatusIndicator progress={r.status === 'failed' ? "Deployment Failed" : "Verification Queued"} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
