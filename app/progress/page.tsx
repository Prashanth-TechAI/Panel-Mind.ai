"use client";

import { DashboardShell, EmptyState, formatDate, useMocks } from "@/components/Dashboard";

/**
 * Progress across attempts.
 *
 * Marks over time is change-over-time, so it is a line — but with a handful of
 * attempts a column per mock reads more honestly than a line implying a trend
 * that three points cannot support.
 */

const MAX_MARKS = 275;

export default function ProgressPage() {
  const mocks = useMocks();
  const marked = (mocks ?? []).filter((m) => m.marks !== null).reverse();

  const best = marked.length ? Math.max(...marked.map((m) => m.marks!)) : 0;
  const latest = marked.length ? marked[marked.length - 1].marks! : 0;
  const average = marked.length
    ? Math.round(marked.reduce((sum, m) => sum + m.marks!, 0) / marked.length)
    : 0;
  const change = marked.length > 1 ? latest - marked[marked.length - 2].marks! : null;

  return (
    <DashboardShell
      title="My progress"
      lede="How your marks have moved across attempts. Compare yourself with yourself — these are not real UPSC marks."
    >
      {mocks === null ? (
        <p className="text-[14px] text-ink-faint">Loading…</p>
      ) : marked.length === 0 ? (
        <EmptyState
          title="No marks yet"
          body="Sit a mock and have the board score it, and your progress will appear here."
        />
      ) : (
        <div className="space-y-8">
          <ul className="grid gap-3 sm:grid-cols-4">
            {[
              ["Latest", latest, change],
              ["Best", best, null],
              ["Average", average, null],
              ["Mocks marked", marked.length, null],
            ].map(([label, value, delta]) => (
              <li key={String(label)} className="card p-5">
                <p className="text-[13px] text-ink-soft">{label}</p>
                <p className="mt-1.5 flex items-baseline gap-2">
                  <span className="text-[28px] font-bold tabular-nums">
                    {String(value)}
                  </span>
                  {typeof delta === "number" && (
                    <span
                      className="text-[13px] font-semibold"
                      style={{
                        color:
                          delta >= 0 ? "var(--color-good)" : "var(--color-danger)",
                      }}
                    >
                      {delta >= 0 ? "+" : ""}
                      {delta}
                    </span>
                  )}
                </p>
              </li>
            ))}
          </ul>

          <div className="card p-6">
            <h2 className="text-[17px] font-semibold">Marks by attempt</h2>
            <p className="mt-1 text-[13px] text-ink-soft">Out of {MAX_MARKS}</p>

            <div className="mt-8 flex items-end gap-4 overflow-x-auto pb-2">
              {marked.map((mock, index) => {
                const height = Math.max(6, (mock.marks! / MAX_MARKS) * 100);
                return (
                  <div
                    key={mock.session_id}
                    className="flex min-w-[64px] flex-1 flex-col items-center gap-3"
                  >
                    <span className="text-[13px] font-semibold tabular-nums">
                      {mock.marks}
                    </span>
                    <div className="flex h-[180px] w-full items-end">
                      <div
                        className="w-full rounded-t-[4px] bg-accent transition-[height] duration-700"
                        style={{ height: `${height}%` }}
                        role="img"
                        aria-label={`Attempt ${index + 1}: ${mock.marks} out of ${MAX_MARKS}`}
                      />
                    </div>
                    <span className="text-center text-[11px] leading-tight text-ink-faint">
                      {formatDate(mock.created_at)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          <p className="text-[13px] leading-relaxed text-ink-faint">
            These marks are produced by an AI board and are not calibrated against
            actual UPSC marks. Use them to track your own improvement, not to
            predict your result.
          </p>
        </div>
      )}
    </DashboardShell>
  );
}
