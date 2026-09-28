"use client";

import Link from "next/link";
import {
  DashboardShell,
  EmptyState,
  formatDate,
  useMocks,
  verdictOf,
} from "@/components/Dashboard";

export default function MocksPage() {
  const mocks = useMocks();

  return (
    <DashboardShell
      title="My mocks"
      lede="Every interview you have sat, newest first. Open any one to re-read the record and your marks."
      action={
        <Link
          href="/daf"
          className="rounded-full bg-accent px-6 py-3 text-[14px] font-semibold text-white transition-colors hover:bg-accent-deep"
        >
          New mock
        </Link>
      }
    >
      {mocks === null ? (
        <p className="text-[14px] text-ink-faint">Loading…</p>
      ) : mocks.length === 0 ? (
        <EmptyState
          title="You haven't faced the board yet"
          body="Fill your DAF and the five members will prepare their questions from it."
        />
      ) : (
        <ul data-testid="mock-list" className="grid gap-3">
          {mocks.map((mock) => {
            const verdict = mock.marks !== null ? verdictOf(mock.marks) : null;

            return (
              <li key={mock.session_id}>
                <Link
                  href={`/report?session=${mock.session_id}`}
                  className="card flex flex-wrap items-center justify-between gap-5 p-5 transition-all hover:shadow-lift"
                >
                  <div className="min-w-0">
                    <p className="text-[15px] font-semibold">
                      {mock.optional_subject} · {mock.home_district}
                    </p>
                    <p className="mt-1 text-[13px] text-ink-soft">
                      {formatDate(mock.created_at)} · {mock.exchanges} exchanges
                      {mock.sat ? "" : " · not sat"}
                    </p>
                  </div>

                  <div className="flex items-center gap-4">
                    {mock.marks !== null && verdict ? (
                      <>
                        <span
                          className="rounded-full px-3 py-1 text-[12px] font-semibold"
                          style={{ background: verdict.tint, color: verdict.ink }}
                        >
                          {verdict.label}
                        </span>
                        <span className="text-[22px] font-bold tabular-nums">
                          {mock.marks}
                          <span className="text-[14px] font-normal text-ink-faint">
                            /275
                          </span>
                        </span>
                      </>
                    ) : (
                      <span className="text-[13px] text-ink-faint">
                        {mock.sat ? "Not marked yet" : "Not sat"}
                      </span>
                    )}
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </DashboardShell>
  );
}
