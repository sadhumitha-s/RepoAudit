import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RepoAudit — ML Reproducibility Scanner",
  description:
    "Automated reproducibility analysis for machine learning research repositories.",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[var(--background)]">
        <header className="border-b border-[var(--border)] bg-[var(--card)]">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
            <a href="/" className="text-xl font-bold text-brand-700">
              RepoAudit
            </a>
            <span className="text-sm text-[var(--muted)]">
              ML Reproducibility Scanner
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}