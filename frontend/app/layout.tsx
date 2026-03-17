import type { Metadata } from "next";
import { Public_Sans } from "next/font/google";
import "./globals.css";

const publicSans = Public_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800", "900"],
  variable: "--font-public-sans",
});

export const metadata: Metadata = {
  title: "RepoAudit | ML Repo Reproducibility Scanner",
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
    <html lang="en" className={publicSans.variable}>
      <body className="min-h-screen bg-[var(--background)] font-sans text-white">
        <header className="border-b-[3px] border-white bg-[#0D1117]">
          <div className="mx-auto flex max-w-5xl items-center px-4 py-4">
            <a href="/" className="text-2xl font-black text-brand-accent tracking-tighter">
              REPOAUDIT.
            </a>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-12">{children}</main>
      </body>
    </html>
  );
}