/**
 * Client for the Python control plane.
 *
 * The FastAPI backend owns all domain logic — board, DAF, conductor,
 * evaluators. This module is the only place the frontend knows its address.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export interface BoardMember {
  id: "M0" | "M1" | "M2" | "M3" | "M4";
  name: string;
  title: string;
  role: string;
  owns: string[];
  weighs: string[];
  accent: string;
}

export interface TraitLabel {
  key: string;
  label: string;
}

export interface BoardResponse {
  members: BoardMember[];
  traits: TraitLabel[];
}

export type ProbeStatus = "ok" | "degraded" | "down";

export interface ProbeResult {
  name: string;
  role: string;
  status: ProbeStatus;
  latency_ms: number;
  detail: string | null;
  hint: string | null;
}

export interface HealthReport {
  status: ProbeStatus;
  checked_at: string;
  deep: boolean;
  total_ms: number;
  providers: ProbeResult[];
}

class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<T>(path: string, revalidateSeconds = 0): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...(revalidateSeconds > 0
      ? { next: { revalidate: revalidateSeconds } }
      : { cache: "no-store" }),
  });

  if (!res.ok && res.status !== 503) {
    throw new ApiError(`GET ${path} failed with ${res.status}`, res.status);
  }

  return (await res.json()) as T;
}

export function getBoard(): Promise<BoardResponse> {
  // Board composition is static; cache it briefly to keep navigation instant.
  return get<BoardResponse>("/api/board", 300);
}

/**
 * Health of every provider. Returns null rather than throwing when the backend
 * itself is unreachable — the page still renders, with the outage stated
 * plainly instead of a crash.
 */
export async function getHealth(deep = false): Promise<HealthReport | null> {
  try {
    return await get<HealthReport>(`/api/health${deep ? "?deep=1" : ""}`);
  } catch {
    return null;
  }
}

export function voiceUrl(memberId: string, text?: string): string {
  const params = new URLSearchParams({ member: memberId });
  if (text) params.set("text", text);
  return `${API_BASE}/api/tts/preview?${params}`;
}
