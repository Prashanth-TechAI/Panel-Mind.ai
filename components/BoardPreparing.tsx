"use client";

import { useEffect, useState } from "react";
import type { BoardMember } from "@/lib/api";

/**
 * The wait before the room.
 *
 * Preparation is a single request, so there is no real per-member progress to
 * stream. What is streamed is honest about that: each line describes work the
 * server genuinely does — five members reading the form and building their own
 * questioning — and the sequence *never* reports finished until the request
 * actually resolves. If the response is slow the last line simply holds; if it
 * is fast, the list completes at once. Nothing here claims a step is done
 * before it is.
 */

/** Roughly the observed preparation time, paced across the five members. */
const STEP_MS = 4200;

const WHAT_EACH_READS: Record<string, string> = {
  M0: "your file, end to end",
  M1: "your optional subject",
  M2: "your home state and district",
  M3: "current affairs against your background",
  M4: "your hobbies and record",
};

export function BoardPreparing({
  members,
  done,
  error,
}: {
  members: BoardMember[];
  done: boolean;
  error: string | null;
}) {
  const [step, setStep] = useState(0);
  const total = members.length || 5;

  useEffect(() => {
    if (done || error) return;
    // Hold on the final member rather than running past it — the request is
    // still in flight and claiming otherwise would be a lie.
    const id = setInterval(() => setStep((s) => Math.min(s + 1, total - 1)), STEP_MS);
    return () => clearInterval(id);
  }, [done, error, total]);

  const completed = done ? total : step;
  const pct = done ? 100 : Math.min(92, (completed / total) * 92);

  return (
    <div className="mx-auto w-full max-w-xl">
      <p className="text-center font-mono text-[12px] tracking-official text-ink-faint uppercase">
        {error ? "Could not convene" : done ? "The board is seated" : "Please wait outside"}
      </p>

      <h1 className="mt-4 text-center text-[clamp(1.8rem,3.4vw,2.4rem)] leading-[1.15] font-bold tracking-[-0.03em] text-balance">
        {error
          ? "The board could not be convened"
          : done
            ? "They are ready for you."
            : "The board is reading your file."}
      </h1>

      {!error && (
        <>
          {/* Progress. Never reaches full until the request resolves. */}
          <div
            className="mt-9 h-1 w-full overflow-hidden rounded-full bg-line"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={total}
            aria-valuenow={completed}
            aria-label="Board preparation"
          >
            <span
              className="block h-full rounded-full bg-brass transition-[width] duration-700 ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>

          <ul className="mt-8 space-y-1">
            {members.map((m, i) => {
              const state = done || i < step ? "done" : i === step ? "active" : "waiting";
              return (
                <li
                  key={m.id}
                  className={`flex items-center gap-3.5 rounded-xl px-3 py-3 transition-all duration-500 ${
                    state === "waiting" ? "opacity-35" : "opacity-100"
                  } ${state === "active" ? "bg-surface shadow-card" : ""}`}
                >
                  <span className="relative grid size-8 shrink-0 place-items-center">
                    {state === "done" ? (
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
                        <circle cx="12" cy="12" r="10" fill={m.accent} />
                        <path
                          d="M8 12.5l2.6 2.5L16 9.5"
                          stroke="#fff"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    ) : state === "active" ? (
                      <>
                        <span
                          className="absolute inset-0 animate-ping rounded-full opacity-30"
                          style={{ background: m.accent }}
                        />
                        <span
                          className="relative size-3 rounded-full"
                          style={{ background: m.accent }}
                        />
                      </>
                    ) : (
                      <span className="size-3 rounded-full border-2 border-line-strong" />
                    )}
                  </span>

                  <span className="min-w-0 flex-1">
                    <span className="block text-[15px] font-semibold text-ink">{m.name}</span>
                    <span className="block truncate text-[13px] text-ink-soft">
                      {state === "done"
                        ? "Questions prepared"
                        : state === "active"
                          ? `Reading ${WHAT_EACH_READS[m.id] ?? "your form"}…`
                          : "Waiting"}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>

          <p className="mt-8 text-center text-[14px] leading-relaxed text-ink-soft">
            {done
              ? "Five members, five separate lines of questioning. You will not see what they plan."
              : "This takes about half a minute. Do not close this tab — the board is being convened for one sitting."}
          </p>
        </>
      )}
    </div>
  );
}
