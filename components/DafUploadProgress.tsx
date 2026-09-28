"use client";

import { useEffect, useState } from "react";

/**
 * Upload feedback, in two honest halves.
 *
 * Sending the file has a real measurable fraction, so it gets a real number.
 * What happens next — rendering the pages, running OCR, matching fields — has
 * no progress feed at all, so it gets a moving indicator and named stages
 * instead. Inventing a percentage for that half would be a lie told at exactly
 * the moment the aspirant is deciding whether to trust the parse.
 */

export type UploadPhase = "sending" | "reading";

const READING_STAGES = [
  "Rendering the pages…",
  "Reading the text…",
  "Finding your personal details…",
  "Matching what it found to the form…",
  "Nearly there…",
];

const STAGE_MS = 2600;

export function DafUploadProgress({
  phase,
  pct,
  fileName,
}: {
  phase: UploadPhase;
  pct: number;
  fileName: string | null;
}) {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    if (phase !== "reading") return;
    // Hold on the last line rather than looping — a cycling message implies
    // progress that is not being observed.
    const id = setInterval(
      () => setStage((s) => Math.min(s + 1, READING_STAGES.length - 1)),
      STAGE_MS,
    );
    return () => clearInterval(id);
  }, [phase]);

  const sending = phase === "sending";

  return (
    <div
      data-testid="upload-progress"
      className="card mt-8 p-6"
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-wrap items-center gap-5">
        <span className="relative grid size-12 shrink-0 place-items-center">
          <svg viewBox="0 0 44 44" className="size-12 -rotate-90" aria-hidden>
            <circle cx="22" cy="22" r="19" fill="none" stroke="var(--color-line)" strokeWidth="4" />
            <circle
              cx="22"
              cy="22"
              r="19"
              fill="none"
              stroke="var(--color-accent)"
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray={2 * Math.PI * 19}
              // While reading there is nothing to measure, so the ring becomes
              // a moving arc rather than a filled fraction.
              strokeDashoffset={
                sending
                  ? 2 * Math.PI * 19 * (1 - Math.min(1, Math.max(0, pct / 100)))
                  : 2 * Math.PI * 19 * 0.75
              }
              className={sending ? "transition-[stroke-dashoffset] duration-300" : "animate-spin origin-center"}
            />
          </svg>
          {sending && (
            <span className="absolute font-mono text-[11px] font-semibold tabular-nums text-accent">
              {Math.round(pct)}
            </span>
          )}
        </span>

        <div className="min-w-[16rem] flex-1">
          <p className="text-[16px] font-semibold text-ink">
            {sending ? "Uploading your form" : "Reading your form"}
          </p>
          <p className="mt-1 text-[14px] leading-relaxed text-ink-soft">
            {sending ? (
              <>
                {Math.round(pct)}% sent
                {fileName && <span className="text-ink-faint"> · {fileName}</span>}
              </>
            ) : (
              READING_STAGES[stage]
            )}
          </p>
        </div>
      </div>

      {/* Determinate while sending; an indeterminate sweep once it is out of
          our hands. */}
      <div className="mt-5 h-1 w-full overflow-hidden rounded-full bg-line">
        {sending ? (
          <span
            className="block h-full rounded-full bg-accent transition-[width] duration-300 ease-out"
            style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
          />
        ) : (
          <span className="animate-sweep block h-full w-1/3 rounded-full bg-brass" />
        )}
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-faint">
        {sending
          ? "Do not close this tab."
          : "Scanned forms take longer than digital ones. Anything it cannot read is left blank for you to fill."}
      </p>
    </div>
  );
}
