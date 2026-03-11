"use client";

import { useState, type FormEvent } from "react";
import { Search, Loader2 } from "lucide-react";

interface Props {
  onSubmit: (url: string) => void;
  loading: boolean;
}

const GITHUB_URL_RE = /^https:\/\/github\.com\/[\w.\-]+\/[\w.\-]+\/?$/;

export function AuditForm({ onSubmit, loading }: Props) {
  const [url, setUrl] = useState("");
  const [validationError, setValidationError] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = url.trim().replace(/\/+$/, "");

    if (!trimmed) {
      setValidationError("Please enter a GitHub URL.");
      return;
    }

    if (!GITHUB_URL_RE.test(trimmed + "/")) {
      setValidationError(
        "Enter a valid GitHub URL (e.g. https://github.com/owner/repo)",
      );
      return;
    }

    setValidationError("");
    onSubmit(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto max-w-2xl">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
          <input
            type="url"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setValidationError("");
            }}
            placeholder="https://github.com/owner/repo"
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] py-3 pl-10 pr-4 text-sm shadow-sm transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            disabled={loading}
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-6 py-3 text-sm font-medium text-white shadow-sm transition-colors hover:bg-brand-700 disabled:opacity-50"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyzing
            </>
          ) : (
            "Audit"
          )}
        </button>
      </div>
      {validationError && (
        <p className="mt-2 text-sm text-[var(--destructive)]">
          {validationError}
        </p>
      )}
    </form>
  );
}