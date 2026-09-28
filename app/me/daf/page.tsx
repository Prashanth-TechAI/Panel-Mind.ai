"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { SiteFooter } from "@/components/SiteFooter";
import { API_BASE } from "@/lib/api";
import { authFetch, getToken, useAuth } from "@/lib/auth";
import { SECTIONS } from "@/lib/daf";

/**
 * Your DAF.
 *
 * Whatever the aspirant gave the board, shown back to them unaltered.
 *
 * A PDF is shown as a PDF — the pages they uploaded, previewed and
 * downloadable. It is not re-typed into our fields and it is not summarised,
 * because the moment we do that they are reading our reading of their form
 * rather than their form.
 *
 * A typed form is shown as its fields, and can be printed as a real DAF-I: the
 * Commission's own eight-page layout, so they can hand it in, mark it up, or
 * take it to a mentor.
 */

interface DafRecord {
  has_daf: boolean;
  source: "form" | "upload" | null;
  updated_at?: number;
  candidate?: string;
  form?: Record<string, string>;
  filename?: string;
  pages?: number;
  fields_read?: number;
  raw_fields?: Record<string, string>;
}

const when = (seconds?: number) =>
  seconds
    ? new Date(seconds * 1000).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : "";

export default function MyDafPage() {
  const router = useRouter();
  const { account, loading } = useAuth();
  const [record, setRecord] = useState<DafRecord | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const res = await authFetch("/api/me/daf");
      if (!res.ok) throw new Error("Your form could not be loaded.");
      setRecord((await res.json()) as DafRecord);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!account) router.replace("/signin?next=/me/daf");
    else void load();
  }, [account, loading, router, load]);

  // The browser fetches a PDF itself and sends no Authorization header, so the
  // token rides in the query string for these two routes only.
  const token = getToken() ?? "";
  const fileUrl = `${API_BASE}/api/me/daf/file?token=${encodeURIComponent(token)}`;
  const exportUrl = `${API_BASE}/api/me/daf/export?token=${encodeURIComponent(token)}`;

  if (loading || busy) {
    return (
      <>
        <AppHeader />
        <main className="flex-1 px-6 py-24 text-center text-[15px] text-ink-faint">
          Fetching your form…
        </main>
        <SiteFooter />
      </>
    );
  }

  const uploaded = record?.source === "upload";

  return (
    <>
      <AppHeader />
      <main className="mx-auto w-full max-w-[1180px] flex-1 px-6 py-12 sm:px-10">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 className="text-[32px] font-bold tracking-[-0.03em]">Your DAF</h1>
            <p className="mt-2 max-w-2xl text-[16px] leading-relaxed text-ink-soft">
              {record?.has_daf
                ? uploaded
                  ? "The form you uploaded, exactly as you gave it to the board."
                  : "The details you entered. The board questions from these and nothing else."
                : "The board has nothing to question you on yet."}
            </p>
          </div>

          {record?.has_daf && (
            <div className="flex flex-wrap items-center gap-3">
              {uploaded ? (
                <>
                  <a
                    href={`${fileUrl}&download=1`}
                    data-testid="daf-download"
                    className="rounded-full bg-accent px-6 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-accent-deep"
                  >
                    Download PDF
                  </a>
                  <Link
                    href="/daf"
                    data-testid="daf-replace"
                    className="rounded-full border border-line px-6 py-3 text-[15px] font-semibold text-ink transition-colors hover:bg-surface-sunk"
                  >
                    Replace
                  </Link>
                </>
              ) : (
                <>
                  <a
                    href={exportUrl}
                    data-testid="daf-export"
                    className="rounded-full bg-accent px-6 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-accent-deep"
                  >
                    Export as DAF-I PDF
                  </a>
                  <Link
                    href="/daf"
                    data-testid="daf-edit"
                    className="rounded-full border border-line px-6 py-3 text-[15px] font-semibold text-ink transition-colors hover:bg-surface-sunk"
                  >
                    Edit
                  </Link>
                </>
              )}
            </div>
          )}
        </div>

        {error && (
          <p role="alert" className="mt-8 rounded-xl bg-danger-wash px-5 py-3.5 text-[14px] text-danger">
            {error}
          </p>
        )}

        {/* --- Nothing given yet --- */}
        {!record?.has_daf && !error && (
          <div className="card mt-10 p-10 text-center" data-testid="daf-empty">
            <p className="text-[18px] font-semibold">No form on file</p>
            <p className="mx-auto mt-2 max-w-md text-[15px] leading-relaxed text-ink-soft">
              Upload your DAF as a PDF, or type it in. Either way it takes a few
              minutes and the board is briefed from it for every mock you sit.
            </p>
            <Link
              href="/daf"
              className="mt-7 inline-block rounded-full bg-accent px-8 py-3.5 text-[15px] font-semibold text-white transition-colors hover:bg-accent-deep"
            >
              Give the board your form
            </Link>
          </div>
        )}

        {/* --- Uploaded: show the PDF itself --- */}
        {record?.has_daf && uploaded && (
          <section className="mt-8" data-testid="daf-upload-view">
            <div className="card flex flex-wrap items-center gap-4 px-6 py-4">
              <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent-wash">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
                     className="text-accent" aria-hidden>
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <path d="M14 2v6h6" />
                </svg>
              </span>
              <div className="min-w-[12rem] flex-1">
                <p className="truncate text-[15px] font-semibold">
                  {record.filename ?? "Your DAF.pdf"}
                </p>
                <p className="mt-0.5 text-[13px] text-ink-soft">
                  {record.pages ? `${record.pages} pages · ` : ""}
                  {record.fields_read ? `${record.fields_read} fields read · ` : ""}
                  Uploaded {when(record.updated_at)}
                </p>
              </div>
              <a
                href={fileUrl}
                target="_blank"
                rel="noreferrer"
                className="text-[14px] font-semibold text-accent hover:underline"
              >
                Open in a new tab
              </a>
            </div>

            {/* The pages themselves. No re-typing, no summary. */}
            <object
              data={fileUrl}
              type="application/pdf"
              data-testid="daf-preview"
              className="mt-5 h-[78vh] w-full rounded-2xl border border-line bg-surface-sunk"
            >
              <div className="p-10 text-center text-[15px] text-ink-soft">
                Your browser cannot display PDFs inline.{" "}
                <a href={fileUrl} className="font-semibold text-accent hover:underline">
                  Open it in a new tab
                </a>{" "}
                instead.
              </div>
            </object>
          </section>
        )}

        {/* --- Typed: show every field --- */}
        {record?.has_daf && !uploaded && (
          <section className="mt-8 space-y-4" data-testid="daf-form-view">
            <p className="text-[14px] text-ink-faint">
              Entered by form · last updated {when(record.updated_at)}
            </p>

            {SECTIONS.map((section) => {
              const filled = section.fields.filter((f) => (record.form ?? {})[f.key]?.trim());
              return (
                <div key={section.title} className="card p-6 sm:p-8">
                  <div className="flex items-baseline justify-between gap-4">
                    <h2 className="text-[19px] font-semibold">{section.title}</h2>
                    <span className="text-[13px] text-ink-faint">
                      {filled.length} of {section.fields.length} given
                    </span>
                  </div>

                  <dl className="mt-6 grid gap-x-8 gap-y-5 sm:grid-cols-2 lg:grid-cols-3">
                    {section.fields.map((f) => {
                      const value = (record.form ?? {})[f.key]?.trim();
                      return (
                        <div key={f.key} className={f.wide ? "sm:col-span-2 lg:col-span-3" : ""}>
                          <dt className="text-[13px] font-medium text-ink-soft">{f.label}</dt>
                          <dd
                            className={`mt-1 text-[15px] ${
                              value ? "text-ink" : "text-ink-faint italic"
                            }`}
                          >
                            {value || "Not given"}
                          </dd>
                        </div>
                      );
                    })}
                  </dl>
                </div>
              );
            })}

            <div className="card flex flex-wrap items-center gap-5 p-6">
              <div className="min-w-[16rem] flex-1">
                <p className="text-[16px] font-semibold">Print it as a real DAF-I</p>
                <p className="mt-1 text-[14px] leading-relaxed text-ink-soft">
                  Your details set in the Commission&rsquo;s own eight-page layout —
                  same numbering, same wording, same sheet.
                </p>
              </div>
              <a
                href={exportUrl}
                className="rounded-full bg-accent px-6 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-accent-deep"
              >
                Export as DAF-I PDF
              </a>
            </div>
          </section>
        )}
      </main>
      <SiteFooter />
    </>
  );
}
