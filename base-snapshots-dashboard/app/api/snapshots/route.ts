import { NextResponse } from "next/server";

export interface SnapshotData {
  id: string;
  network: "mainnet" | "sepolia";
  client: string;
  type: "pruned" | "archive" | "proofs";
  filename: string | null;
  downloadUrl: string | null;
  sizeBytes: number | null;
  lastModified: string | null;
  unixTimestamp: number | null;
  blockNumber: number | null;
  tab: "mainnet" | "sepolia";
  status: "available" | "unavailable" | "error";
}

interface SnapshotConfig {
  id: string;
  network: "mainnet" | "sepolia";
  client: string;
  type: "pruned" | "archive" | "proofs";
  baseUrl: string;
  tab: "mainnet" | "sepolia";
}

const SNAPSHOT_CONFIGS: SnapshotConfig[] = [
  // Mainnet
  {
    id: "mainnet-reth-pruned",
    network: "mainnet",
    client: "reth",
    type: "pruned",
    baseUrl: "https://mainnet-reth-pruned-snapshots.base.org",
    tab: "mainnet",
  },
  {
    id: "mainnet-reth-archive",
    network: "mainnet",
    client: "reth",
    type: "archive",
    baseUrl: "https://mainnet-reth-archive-snapshots.base.org",
    tab: "mainnet",
  },
  {
    id: "mainnet-reth-proofs",
    network: "mainnet",
    client: "reth",
    type: "proofs",
    baseUrl: "https://mainnet-reth-proofs-snapshots.base.org",
    tab: "mainnet",
  },
  // Sepolia
  {
    id: "sepolia-reth-pruned",
    network: "sepolia",
    client: "reth",
    type: "pruned",
    baseUrl: "https://sepolia-reth-pruned-snapshots.base.org",
    tab: "sepolia",
  },
  {
    id: "sepolia-reth-archive",
    network: "sepolia",
    client: "reth",
    type: "archive",
    baseUrl: "https://sepolia-reth-archive-snapshots.base.org",
    tab: "sepolia",
  },
  {
    id: "sepolia-reth-proofs",
    network: "sepolia",
    client: "reth",
    type: "proofs",
    baseUrl: "https://sepolia-reth-proofs-snapshots.base.org",
    tab: "sepolia",
  },
];

const RPC: Record<"mainnet" | "sepolia", string> = {
  mainnet: "https://mainnet.base.org",
  sepolia: "https://sepolia.base.org",
};

async function getLatestBlock(network: "mainnet" | "sepolia"): Promise<{ number: number; timestamp: number } | null> {
  try {
    const res = await fetch(RPC[network], {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "eth_getBlockByNumber", params: ["latest", false] }),
      cache: "no-store",
    });
    const { result } = await res.json();
    return {
      number: parseInt(result.number, 16),
      timestamp: parseInt(result.timestamp, 16),
    };
  } catch {
    return null;
  }
}

function estimateBlock(
  anchor: { number: number; timestamp: number },
  targetTimestamp: number
): number {
  // Base has a consistent 2-second block time
  return Math.max(1, anchor.number - Math.round((anchor.timestamp - targetTimestamp) / 2));
}

async function fetchSnapshotData(config: SnapshotConfig): Promise<Omit<SnapshotData, "blockNumber">> {
  try {
    const latestRes = await fetch(`${config.baseUrl}/latest`, { cache: "no-store" });

    if (!latestRes.ok) {
      return { ...config, filename: null, downloadUrl: null, sizeBytes: null, lastModified: null, unixTimestamp: null, status: "unavailable" };
    }

    const filename = (await latestRes.text()).trim();
    const downloadUrl = `${config.baseUrl}/${filename}`;

    const headRes = await fetch(downloadUrl, { method: "HEAD", cache: "no-store" });

    const contentLength = headRes.headers.get("content-length");
    const sizeBytes = contentLength ? parseInt(contentLength) : null;
    const lastModified = headRes.headers.get("last-modified");

    const match = filename.match(/(\d{10})\.tar\.zst$/);
    const unixTimestamp = match ? parseInt(match[1]) : null;

    return { ...config, filename, downloadUrl, sizeBytes, lastModified, unixTimestamp, status: "available" };
  } catch {
    return { ...config, filename: null, downloadUrl: null, sizeBytes: null, lastModified: null, unixTimestamp: null, status: "error" };
  }
}

export async function GET() {
  const [[mainnetAnchor, sepoliaAnchor], rawSnapshots] = await Promise.all([
    Promise.all([getLatestBlock("mainnet"), getLatestBlock("sepolia")]),
    Promise.all(SNAPSHOT_CONFIGS.map(fetchSnapshotData)),
  ]);

  const anchors = { mainnet: mainnetAnchor, sepolia: sepoliaAnchor };

  const snapshots: SnapshotData[] = rawSnapshots.map((s) => {
    const anchor = anchors[s.network];
    const blockNumber =
      anchor && s.unixTimestamp ? estimateBlock(anchor, s.unixTimestamp) : null;
    return { ...s, blockNumber };
  });

  return NextResponse.json({ snapshots, fetchedAt: new Date().toISOString() });
}
