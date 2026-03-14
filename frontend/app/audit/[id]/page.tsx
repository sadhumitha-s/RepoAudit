import type { Metadata } from "next";
import { AuditDetail } from "./AuditDetail";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:7860";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://repo-audit.vercel.app";

interface Props {
  params: Promise<{ id: string }>;
}

async function fetchAuditForMeta(id: string) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/audit/${encodeURIComponent(id)}`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const audit = await fetchAuditForMeta(id);

  if (!audit?.report) {
    return {
      title: "Audit — RepoAudit",
      description: "ML reproducibility audit results.",
    };
  }

  const repoUrl: string = audit.repo_url ?? "";
  const match = repoUrl.match(/github\.com\/([^/]+)\/([^/]+)/);
  const repoName = match ? `${match[1]}/${match[2]}` : repoUrl;
  const score = Math.round(audit.report.total_score ?? 0);
  const summary: string = audit.report.summary ?? "";
  const commit = audit.commit_hash ? ` · ${String(audit.commit_hash).slice(0, 7)}` : "";

  const title = `${repoName} — Score ${score}/100 · RepoAudit`;
  const description = summary
    ? `${summary} (Score: ${score}/100${commit})`
    : `Reproducibility score: ${score}/100${commit}`;

  const pageUrl = `${SITE_URL}/audit/${id}`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: pageUrl,
      siteName: "RepoAudit",
      type: "article",
    },
    twitter: {
      card: "summary",
      title,
      description,
    },
    alternates: {
      canonical: pageUrl,
    },
  };
}

export default async function AuditPage({ params }: Props) {
  const { id } = await params;
  return <AuditDetail id={id} />;
}