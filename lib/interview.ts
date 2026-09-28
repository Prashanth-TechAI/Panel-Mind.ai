import { API_BASE } from "@/lib/api";
import { authFetch } from "@/lib/auth";

/**
 * Interview session lifecycle, browser side.
 *
 * Everything slow happens in `createSession` — the board reads the DAF and
 * prepares five question trees before the candidate is ever in the room.
 */

export interface SessionCredentials {
  session_id: string;
  room: string;
  token: string;
  livekit_url: string;
  prepared_members: string[];
  failures: string[];
  total_questions: number;
}

export interface BoardState {
  phase: "idle" | "chairman_opening" | "member_block" | "chairman_closing" | "ended";
  mic_holder: string | null;
  elapsed_ms: number;
  questions_in_block: number;
  completed_blocks: string[];
  pending_members: string[];
  ended_reason: string | null;
}

export interface Utterance {
  speaker: string;
  member_id: string | null;
  text: string;
  at_ms: number;
  turn: number;
}

export const STATE_TOPIC = "board.state";
export const TRANSCRIPT_TOPIC = "board.transcript";

const STORAGE_KEY = "upsc.board.session";

export interface DafPayload {
  full_name: string;
  home_state: string;
  home_district: string;
  education: { graduation_subject: string; graduation_college: string };
  optional_subject: string;
  hobbies: string[];
  service_preference: string[];
  work_experience: string[];
  positions_of_responsibility: string[];
  attempt_number: number;
}

export async function createSession(daf: DafPayload): Promise<SessionCredentials> {
  // Signed so the interview is filed against the aspirant's account.
  const res = await authFetch("/api/session", {
    method: "POST",
    body: JSON.stringify(daf),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail ?? body?.error;
    const message = Array.isArray(detail)
      ? `${detail[0]?.loc?.slice(1).join(".")} — ${detail[0]?.msg}`
      : (detail ?? `Could not convene the board (${res.status})`);
    throw new Error(String(message));
  }

  return (await res.json()) as SessionCredentials;
}

/** Handed from the DAF page to the room. Cleared once the room has it. */
export function stashSession(credentials: SessionCredentials): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(credentials));
}

export function takeSession(): SessionCredentials | null {
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionCredentials;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}

export function formatClock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = String(Math.floor(total / 60)).padStart(2, "0");
  const seconds = String(total % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export const PHASE_LABEL: Record<BoardState["phase"], string> = {
  idle: "Waiting outside",
  chairman_opening: "Chairman opening",
  member_block: "Under questioning",
  chairman_closing: "Chairman closing",
  ended: "Interview over",
};
