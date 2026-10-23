"use client";

import { useState, useEffect, useCallback } from "react";
import type { SnapshotData } from "./api/snapshots/route";

interface ApiResponse {
  snapshots: SnapshotData[];
  fetchedAt: string;
}

type Tab = "mainnet" | "sepolia";

const DOCS_URL = "https://docs.base.org";
const GITHUB_URL = "https://github.com/base/base-snapshots-dashboard";
const SNAPSHOTS_DOCS_URL = "https://docs.base.org/base-chain/node-operators/snapshots";

const BASESCAN: Record<string, string> = {
  mainnet: "https://basescan.org",
  sepolia: "https://sepolia.basescan.org",
};

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes >= 1e12) return `${(bytes / 1e12).toFixed(2)} TB`;
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  return `${bytes} B`;
}

function formatAge(unixSeconds: number | null): string {
  if (!unixSeconds) return "—";
  const days = Math.floor((Date.now() - unixSeconds * 1000) / 86400000);
  const hours = Math.floor((Date.now() - unixSeconds * 1000) / 3600000);
  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  return "< 1h ago";
}

function formatDate(unixSeconds: number | null): string {
  if (!unixSeconds) return "—";
  return new Date(unixSeconds * 1000).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function formatBlock(n: number | null): string {
  if (!n) return "—";
  return n.toLocaleString("en-US");
}

function CopyButton({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button
      onClick={copy}
      title="Copy download URL"
      className="text-icon-muted hover:text-icon-hover dark:hover:text-icon-dark-hover transition-colors"
    >
      {copied ? (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ) : (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      )}
    </button>
  );
}

// Fixed column widths — never change between tabs to avoid layout shift
const COLS = "grid-cols-[90px_100px_80px_120px_140px_1fr]";

function TableHeader() {
  const headers = ["Type", "Size", "Age", "Date (UTC)", "Block", ""];
  return (
    <div className={`grid ${COLS} gap-x-4 px-5 py-3 border-b border-[#ebebeb] dark:border-[#21262d]`}>
      {headers.map((h, i) => (
        <div
          key={i}
          className={`text-[11px] font-bold uppercase tracking-wider text-table-subtle dark:text-table-dark-subtle ${i === 5 ? "text-right" : ""}`}
        >
          {h}
        </div>
      ))}
    </div>
  );
}

function TableRow({ snapshot }: { snapshot: SnapshotData }) {
  const ok = snapshot.status === "available";
  return (
    <div className={`grid ${COLS} gap-x-4 px-5 py-3.5 border-b border-[#ebebeb] dark:border-[#21262d] last:border-b-0 hover:bg-[#fafafa] dark:hover:bg-[#161b22] transition-colors items-center`}>
      <div className="text-sm text-table dark:text-table-dark capitalize">{snapshot.type}</div>
      <div className="text-sm font-mono text-table dark:text-table-dark">
        {ok ? formatBytes(snapshot.sizeBytes) : <span className="text-xs text-table-subtle dark:text-table-dark-subtle">{snapshot.status}</span>}
      </div>
      <div className="text-sm text-table dark:text-table-dark">{formatAge(snapshot.unixTimestamp)}</div>
      <div className="text-sm font-mono text-table dark:text-table-dark">{formatDate(snapshot.unixTimestamp)}</div>
      <div className="text-sm font-mono text-table dark:text-table-dark">
        {snapshot.blockNumber ? (
          <a
            href={`${BASESCAN[snapshot.network]}/block/${snapshot.blockNumber}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-link dark:hover:text-link-dark transition-colors"
          >
            {formatBlock(snapshot.blockNumber)}
          </a>
        ) : "—"}
      </div>
      <div className="flex items-center justify-end gap-2">
        {ok && snapshot.downloadUrl ? (
          <>
            <CopyButton url={snapshot.downloadUrl} />
            <a
              href={snapshot.downloadUrl}
              className="text-sm text-link dark:text-link-dark dark:hover:text-link-dark-hover hover:underline"
            >
              Download
            </a>
          </>
        ) : (
          <span className="text-xs text-table-subtle dark:text-table-dark-subtle">—</span>
        )}
      </div>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className={`grid ${COLS} gap-x-4 px-5 py-3.5 border-b border-[#ebebeb] dark:border-[#21262d] last:border-b-0 items-center`}>
      {[56, 68, 44, 88, 84, 60].map((w, i) => (
        <div key={i} className={`flex ${i === 5 ? "justify-end" : ""}`}>
          <div className="h-3.5 bg-[#f0f0f0] dark:bg-[#21262d] rounded animate-pulse" style={{ width: w }} />
        </div>
      ))}
    </div>
  );
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("mainnet");
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (stored === "dark" || (!stored && prefersDark)) {
      document.documentElement.classList.add("dark");
      setDark(true);
    }
  }, []);

  const toggleDark = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/snapshots");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const tabSnapshots = data?.snapshots.filter((s) => s.tab === activeTab) ?? [];
  const skeletonCount = 4;

  const TABS: { id: Tab; label: string }[] = [
    { id: "mainnet", label: "Mainnet" },
    { id: "sepolia", label: "Sepolia" },
  ];

  return (
    <div className="min-h-screen bg-white dark:bg-[#0f1117] text-content dark:text-content-dark">

      {/* Header */}
      <header className="border-b border-[#ebebeb] dark:border-[#21262d]">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-4 h-4 bg-brand flex-shrink-0" />
            <span className="text-xl tracking-tight text-[#000] dark:text-white">
              <span className="font-bold">base</span><span className="font-normal ml-1.5">snapshots</span>
            </span>
          </div>
          <div className="flex items-center gap-4">
            <a
              href={DOCS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-content-subtle dark:text-content-dark-subtle hover:text-[#000] dark:hover:text-white transition-colors hidden sm:block"
            >
              Docs
            </a>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              title="View on GitHub"
              className="text-content-subtle dark:text-content-dark-subtle hover:text-[#000] dark:hover:text-white transition-colors hidden sm:block"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.009-.868-.013-1.703-2.782.604-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836a9.59 9.59 0 0 1 2.504.337c1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.741 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z"/>
              </svg>
            </a>
            <button
              onClick={toggleDark}
              title={dark ? "Light mode" : "Dark mode"}
              className="text-content-subtle dark:text-content-dark-subtle hover:text-[#000] dark:hover:text-white transition-colors"
            >
              {dark ? (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/>
                  <line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/>
                  <line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                </svg>
              ) : (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                </svg>
              )}
            </button>
            <button
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-1.5 text-sm text-content-subtle dark:text-content-dark-subtle hover:text-[#000] dark:hover:text-white disabled:opacity-40 transition-colors"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={loading ? "animate-spin" : ""}>
                <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
              </svg>
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">

        {/* Title */}
        <div className="mb-6">
          <p className="text-sm text-content dark:text-content-dark">
            Pre-built snapshots for faster node sync using reth, compressed with zstd.{" "}
            <a href={SNAPSHOTS_DOCS_URL} target="_blank" rel="noopener noreferrer" className="text-link dark:text-link-dark dark:hover:text-link-dark-hover hover:underline">
              View setup instructions →
            </a>
          </p>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[#ebebeb] dark:border-[#21262d] mb-0">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm border-b-2 -mb-px transition-colors ${
                activeTab === tab.id
                  ? "border-link dark:border-link-dark text-link dark:text-link-dark dark:hover:text-link-dark-hover font-medium"
                  : "border-transparent text-content-subtle dark:text-content-dark-subtle hover:text-[#000] dark:hover:text-white"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="border border-[#ebebeb] dark:border-[#21262d] border-t-0 rounded-b-[10px] overflow-hidden">
          <TableHeader />
          {error ? (
            <div className="py-10 text-center">
              <p className="text-sm text-content dark:text-content-dark mb-3">{error}</p>
              <button onClick={fetchData} className="text-sm text-link dark:text-link-dark dark:hover:text-link-dark-hover hover:underline">Retry</button>
            </div>
          ) : loading ? (
            Array.from({ length: skeletonCount }).map((_, i) => <SkeletonRow key={i} />)
          ) : tabSnapshots.length === 0 ? (
            <div className="py-10 text-center text-sm text-content dark:text-content-dark">No snapshots available</div>
          ) : (
            tabSnapshots.map((s) => <TableRow key={s.id} snapshot={s} />)
          )}
        </div>

        {/* Footnote */}
        <p className="mt-4 text-xs text-content-subtle dark:text-content-dark-subtle">
          Extract with{" "}
          <code className="font-mono bg-[#fafafa] dark:bg-[#161b22] border border-[#ebebeb] dark:border-[#21262d] px-1 rounded">
            tar -I zstd -xf &lt;file&gt;
          </code>
          . Block numbers are estimates based on a 2-second block time.
        </p>

      </main>
    </div>
  );
}
