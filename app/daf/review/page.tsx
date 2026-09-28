"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { SiteFooter } from "@/components/SiteFooter";
import {
  REQUIRED,
  SECTIONS,
  readDafDraft,
  type DafForm,
} from "@/lib/daf";

/**
 * The last screen before the room.
 *
 * Two jobs, and only two. Let the aspirant catch a misread field — which
 * matters most after an upload, where OCR turns a district into a different
 * district and the whole interview then interrogates the wrong place. And
 * state the stakes of convening, because a room is built for one sitting.
 *
 * It deliberately does not say which member owns which topic. A real board
 * never tells you that, and knowing it lets you rehearse for whoever is about
 * to speak — removing the exact pressure this product exists to reproduce.
 */

export default function DafReviewPage() {
  const router = useRouter();
  const [draft, setDraft] = useState<{
    form: DafForm;
    fromUpload: boolean;
    rawFields?: Record<string, string>;
  } | null>(null);
  const [checked, setChecked] = useState(false);
  const [convening, setConvening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Read once on mount. Without a draft there is nothing to review, so send
  // them back rather than showing an empty page.
  useEffect(() => {
    const d = readDafDraft();
    if (!d) router.replace("/daf");
    else setDraft(d);
  }, [router]);

  if (!draft) {
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

  const { form, fromUpload, rawFields } = draft;

  // A PDF is shown as it was read. Only a typed form is shown as our fields,
  // because only a typed form has our fields.
  const readFromPdf = Object.entries(rawFields ?? {}).filter(([, v]) => String(v).trim());

  if (fromUpload && readFromPdf.length > 0) {
    return (
      <>
        <AppHeader />
        <main className="mx-auto w-full max-w-[1100px] flex-1 px-6 py-12 sm:px-10">
          <Link href="/daf" className="text-[14px] font-medium text-ink-soft hover:text-ink">
            ‹ Back to the form
          </Link>

          <h1 className="mt-6 text-[32px] font-bold tracking-[-0.03em]">What the board has</h1>
          <p className="mt-2 max-w-2xl text-[16px] leading-relaxed text-ink-soft">
            Read straight off your PDF, in the form&rsquo;s own words — all{" "}
            {readFromPdf.length} of them. Scans mislead, so check the district,
            the years and the spellings: a wrong entry here becomes a wrong
            question in the room.
          </p>

          <dl className="card mt-8 divide-y divide-line p-2">
            {readFromPdf.map(([label, value]) => (
              <div key={label} className="grid gap-1 px-5 py-3.5 sm:grid-cols-[minmax(0,22rem)_1fr] sm:gap-6">
                <dt className="text-[13px] leading-relaxed text-ink-soft">{label}</dt>
                <dd className="text-[15px] leading-relaxed font-medium text-ink">{String(value)}</dd>
              </div>
            ))}
          </dl>

          <div className="mt-10 flex flex-wrap items-center gap-5 rounded-2xl border border-line bg-surface p-6">
            <button
              type="button"
              onClick={convene}
              disabled={convening}
              data-testid="convene"
              className="rounded-full bg-accent px-8 py-3.5 text-[15px] font-semibold text-white transition-colors hover:bg-accent-deep disabled:opacity-60"
            >
              {convening ? "The board is reading your file…" : "Convene the board"}
            </button>
            <span className="max-w-sm text-[14px] leading-relaxed text-ink-soft">
              All {readFromPdf.length} fields go to the board. They divide them
              between themselves before you walk in.
            </span>
          </div>
        </main>
        <SiteFooter />
      </>
    );
  }

  const blanks = SECTIONS.flatMap((s) => s.fields).filter((f) => !form[f.key]?.trim());
  const requiredBlanks = blanks.filter((f) => REQUIRED.has(f.key));

  function convene() {
    setConvening(true);
    setError(null);
    // The draft is already stashed; the interview page convenes from it so the
    // half-minute wait gets a screen of its own rather than a spinning button.
    router.push("/interview");
  }

  return (
    <>
      <AppHeader />

      <main className="mx-auto w-full max-w-[1000px] flex-1 px-6 py-12 sm:px-10">
        <Link
          href="/daf"
          className="inline-flex items-center gap-2 text-[14px] font-medium text-ink-soft transition-colors hover:text-ink"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path
              d="M15 5l-7 7 7 7"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Back to the form
        </Link>

        <h1 className="mt-6 text-[32px] font-bold tracking-[-0.03em]">
          What the board has
        </h1>
        <p className="mt-2 max-w-2xl text-[16px] leading-relaxed text-ink-soft">
          {fromUpload
            ? "This is what we read off your PDF. Scans mislead — check the district, the years and the spellings especially, because a wrong entry here becomes a wrong question in the room."
            : "They question from this and nothing else. Read it once before you go in: anything blank is ground they cannot cover."}
        </p>

        {!fromUpload && blanks.length > 0 && (
          <div className="mt-7 rounded-2xl border border-line bg-warn-wash p-5">
            <p className="text-[15px] font-semibold text-warn">
              {blanks.length} field{blanks.length > 1 ? "s" : ""} left blank
            </p>
            <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-ink-soft">
              {requiredBlanks.length > 0
                ? "Some of these are ones the board leans on hardest. You can go in without them, but expect a thinner interview."
                : "Not a problem — the board simply has less to work with in those areas."}
            </p>
            <Link
              href="/daf"
              className="mt-3 inline-block text-[14px] font-semibold text-accent-bright hover:underline"
            >
              Go back and fill them
            </Link>
          </div>
        )}

        <div className="mt-8 space-y-5">
          {SECTIONS.map((section) => (
            <section key={section.title} className="card p-6">
              <h2 className="text-[16px] font-semibold text-ink">{section.title}</h2>
              <dl className="mt-4 grid gap-x-8 gap-y-4 sm:grid-cols-2">
                {section.fields.map((f) => {
                  const value = form[f.key]?.trim();
                  return (
                    <div key={f.key} className={f.wide ? "sm:col-span-2" : undefined}>
                      <dt className="text-[12px] font-medium text-ink-faint">{f.label}</dt>
                      <dd
                        className={`mt-0.5 text-[14px] leading-relaxed ${
                          value ? "text-ink" : "text-ink-faint italic"
                        }`}
                      >
                        {value || "Not provided"}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            </section>
          ))}
        </div>

        {/* --- Commit --- */}
        <div className="mt-10 rounded-3xl border border-line bg-surface p-7 shadow-card sm:p-8">
          <h2 className="text-[20px] font-bold tracking-[-0.02em]">Ready to sit it?</h2>
          <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
            Five members will read this and prepare their own questioning before
            you enter. You will not see what they plan.
          </p>

          <label className="mt-5 flex max-w-2xl cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
              data-testid="confirm-read"
              className="mt-0.5 size-4 shrink-0 accent-[var(--color-accent)]"
            />
            <span className="text-[14px] leading-relaxed text-ink-soft">
              I have checked the form above, and I understand the board is
              convened once — if I leave the room, that attempt is over.
            </span>
          </label>

          {error && (
            <p
              role="alert"
              data-testid="convene-error"
              className="mt-5 rounded-xl bg-danger-wash px-4 py-3 text-[14px] text-danger"
            >
              {error}
            </p>
          )}

          <div className="mt-6 flex flex-wrap items-center gap-4">
            <button
              type="button"
              onClick={convene}
              disabled={convening || !checked}
              data-testid="convene"
              className="rounded-full bg-accent px-8 py-3.5 text-[15px] font-semibold text-white transition-colors hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-40"
            >
              {convening ? "Taking you through…" : "Convene the board"}
            </button>
            <span className="max-w-sm text-[13px] leading-relaxed text-ink-soft">
              {convening
                ? "Five members are preparing their questions. About half a minute."
                : "Takes about half a minute to prepare."}
            </span>
          </div>
        </div>
      </main>

      <SiteFooter />
    </>
  );
}
