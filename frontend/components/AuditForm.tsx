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
    <form onSubmit={handleSubmit} className="mx-auto max-w-2xl mt-12 mb-16">
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <label htmlFor="repo-url" className="sr-only">
            GitHub repository URL
          </label>
          <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
          <input
            id="repo-url"
            name="repoUrl"
            type="url"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setValidationError("");
            }}
            placeholder="https://github.com/owner/repo"
            autoComplete="url"
            aria-invalid={Boolean(validationError)}
            aria-describedby={validationError ? "repo-url-error" : undefined}
            className="w-full h-14 neo-border bg-[#0D1117] text-white py-3 pl-12 pr-4 text-base shadow-neo focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-brand-accent transition-none placeholder:text-gray-500"
            disabled={loading}
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="neo-button h-14 px-8 text-base tracking-wide flex items-center justify-center gap-2 "
        >
          {loading ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              ANALYZING
            </>
          ) : (
            "AUDIT REPO"
          )}
        </button>
      </div>
      {validationError && (
        <div
          id="repo-url-error"
          className="mt-4 neo-border bg-red-500 text-white p-3 font-medium text-sm inline-block shadow-neo"
        >
          {validationError}
        </div>
      )}
    </form>
  );
}
