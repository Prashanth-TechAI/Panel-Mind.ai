"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { IconClock, IconForm } from "@/components/Icons";
import { useMocks, type Mock } from "@/components/Dashboard";
import { API_BASE } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formFromDaf, stashDafDraft } from "@/lib/daf";

/**
 * Pick up where you left off.
 *
 * An aspirant who filled a long form and then walked away should not have to
 * fill it again. This finds their most recent unfinished attempt and offers to
 * convene a board from the same file.
 *
 * It says "start again from this form", not "resume the interview", because
 * that is what actually happens: a room is built for one sitting and cannot be
 * re-entered, so a fresh board is convened from the stored DAF. Claiming to
 * resume a room we cannot resume would be a lie the first click exposes.
 */

/** Never sat, or sat but never marked — either way, unfinished business. */
function unfinished(m: Mock): boolean {
  return !m.sat || m.marks === null;
}

function whenLabel(seconds: number): string {
  const days = Math.floor((Date.now() / 1000 - seconds) / 86_400);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return new Date(seconds * 1000).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
  });
}

export function ResumeMock() {
  const { account } = useAuth();
  const mocks = useMocks();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const latest = (mocks ?? []).filter(unfinished)[0];

  async function resume() {
    if (!latest) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/session/${latest.session_id}`);
      const body = await res.json().catch(() => null);
      if (!res.ok || !body?.daf) {
        throw new Error(
          "That attempt has expired. Its form is no longer held — please fill it again.",
        );
      }
      stashDafDraft({ form: formFromDaf(body.daf), fromUpload: false });
      router.push("/interview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reopen that attempt.");
      setBusy(false);
    }
  }

  // Signed out, still loading, or nothing unfinished — the ordinary entry.
  if (!account || !mocks || !latest) {
    return (
      <Link
        href="/daf"
        className="group flex max-w-xl items-center gap-4 rounded-2xl border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-lift"
      >
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent-wash text-accent">
          <IconForm className="size-5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[15px] font-semibold text-ink">
            Start from your application form
          </span>
          <span className="block text-[13px] text-ink-soft">
            Three minutes, then the board reads it and prepares
          </span>
        </span>
        <span className="text-ink-faint transition-transform group-hover:translate-x-1">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M5 12h14m-6-6l6 6-6 6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </Link>
    );
  }

  return (
    <div
      data-testid="resume-card"
      className="max-w-xl rounded-2xl border border-brass/40 bg-surface p-4 shadow-card"
    >
      <div className="flex items-center gap-4">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brass/15 text-brass">
          <IconClock className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold text-ink">
            {latest.sat ? "You left an interview unfinished" : "You never sat this one"}
          </p>
          <p className="mt-0.5 truncate text-[13px] text-ink-soft">
            {latest.optional_subject} · {latest.home_district} · {whenLabel(latest.created_at)}
            {latest.sat && ` · ${latest.exchanges} exchanges`}
          </p>
        </div>
      </div>

      {error && (
        <p role="alert" data-testid="resume-error" className="mt-3 rounded-xl bg-danger-wash px-3.5 py-2.5 text-[13px] text-danger">
          {error}
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={resume}
          disabled={busy}
          data-testid="resume-go"
          className="rounded-full bg-accent px-6 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-accent-deep disabled:opacity-50"
        >
          {busy ? "Reopening your file…" : "Continue with this form"}
        </button>
        <Link
          href="/daf"
          className="text-[14px] font-medium text-ink-soft transition-colors hover:text-ink"
        >
          Start a new form
        </Link>
      </div>

      <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">
        A room is convened for one sitting, so a fresh board is seated — from
        this same form, with nothing to fill in again.
      </p>
    </div>
  );
}
