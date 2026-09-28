"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { SiteFooter } from "@/components/SiteFooter";
import { authFetch, useAuth } from "@/lib/auth";

/**
 * Shared shell for the signed-in area.
 *
 * Handles the two states every dashboard page needs — checking the session and
 * being signed out — so each page only writes its own content.
 */

export interface Mock {
  session_id: string;
  candidate: string;
  optional_subject: string;
  home_district: string;
  created_at: number;
  exchanges: number;
  ended_reason: string | null;
  marks: number | null;
  sat: boolean;
}

export function useMocks() {
  const [mocks, setMocks] = useState<Mock[] | null>(null);
  const { account } = useAuth();

  useEffect(() => {
    if (!account) return;
    authFetch("/api/me/mocks")
      .then((r) => (r.ok ? r.json() : { mocks: [] }))
      .then((body) => setMocks(body.mocks as Mock[]))
      .catch(() => setMocks([]));
  }, [account]);

  return mocks;
}

export function formatDate(seconds: number): string {
  return new Date(seconds * 1000).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function DashboardShell({
  title,
  lede,
  action,
  children,
}: {
  title: string;
  lede: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  const { account, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !account) router.replace(`/signin?next=${window.location.pathname}`);
  }, [loading, account, router]);

  return (
    <>
      <AppHeader />
      <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-12 sm:px-10">
        {loading || !account ? (
          <div className="py-24 text-center text-[14px] text-ink-faint">
            Checking your session…
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h1 className="text-[30px] font-bold tracking-[-0.03em]">{title}</h1>
                <p className="mt-2 max-w-lg text-[15px] leading-relaxed text-ink-soft">
                  {lede}
                </p>
              </div>
              {action}
            </div>
            <div className="mt-10">{children}</div>
          </>
        )}
      </main>
      <SiteFooter />
    </>
  );
}

export function EmptyState({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div className="card flex flex-col items-center px-8 py-16 text-center">
      <p className="text-[17px] font-semibold">{title}</p>
      <p className="mt-2 max-w-sm text-[14px] leading-relaxed text-ink-soft">{body}</p>
      <Link
        href="/daf"
        className="mt-7 rounded-full bg-accent px-6 py-3 text-[14px] font-semibold text-white transition-colors hover:bg-accent-deep"
      >
        Start a mock interview
      </Link>
    </div>
  );
}

/** Marks out of 275, banded the way real reported marks fall. */
export function verdictOf(marks: number): { label: string; tint: string; ink: string } {
  if (marks >= 200) return { label: "Very strong", tint: "var(--color-good-wash)", ink: "var(--color-good)" };
  if (marks >= 175) return { label: "Good", tint: "var(--color-good-wash)", ink: "var(--color-good)" };
  if (marks >= 150) return { label: "Average", tint: "var(--color-warn-wash)", ink: "var(--color-warn)" };
  return { label: "Below the bar", tint: "var(--color-danger-wash)", ink: "var(--color-danger)" };
}
