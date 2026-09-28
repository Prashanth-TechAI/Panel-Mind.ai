"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { SiteFooter } from "@/components/SiteFooter";
import { API_BASE } from "@/lib/api";
import { authFetch, authUpload, useAuth } from "@/lib/auth";
import { DafUploadProgress, type UploadPhase } from "@/components/DafUploadProgress";
import {
  EMPTY,
  REQUIRED,
  SECTIONS,
  SPECIMEN,
  dafPayload,
  formFromUpload,
  stashDafDraft,
  type DafForm,
} from "@/lib/daf";

/**
 * DAF intake.
 *
 * Two ways in, one destination. Upload the scanned form and it is read for you;
 * or type it. Either way the fields are the real DAF's own, because the board
 * questions from nothing else — and anything the scan could not read is shown
 * as an unanswered field rather than quietly left blank.
 */

const inputClass =
  "mt-1.5 w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-[15px] text-ink outline-none transition-all placeholder:text-ink-faint focus:border-accent focus:ring-4 focus:ring-accent/10";

export default function DafPage() {
  const router = useRouter();
  const { account } = useAuth();
  const [form, setForm] = useState<DafForm>(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadPhase, setUploadPhase] = useState<UploadPhase>("sending");
  const [uploadPct, setUploadPct] = useState(0);
  const [uploadName, setUploadName] = useState<string | null>(null);
  const [uploadNote, setUploadNote] = useState<string | null>(null);
  const [missing, setMissing] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fromUpload, setFromUpload] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (account?.name) setForm((f) => (f.full_name ? f : { ...f, full_name: account.name }));
  }, [account]);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((p) => ({ ...p, [k]: e.target.value }));


  /** Validate server-side, then hand the draft to the review step. */
  /** Placeholder for a field the scan could not supply. Visible, not silent. */
  const NOT_STATED = "Not stated";

  async function review(
    nextForm: DafForm,
    cameFromUpload: boolean,
    rawFields?: Record<string, string>,
  ) {
    // The board can question around a gap, but validation cannot accept a
    // blank. Mark it so the review shows it as unanswered rather than failing.
    if (cameFromUpload) {
      for (const key of ["full_name", "home_state", "home_district",
                         "graduation_subject", "graduation_college",
                         "optional_subject", "hobbies", "service_preference"]) {
        if (!nextForm[key]?.trim()) nextForm = { ...nextForm, [key]: NOT_STATED };
      }
    }
    const res = await fetch(`${API_BASE}/api/daf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dafPayload(nextForm)),
    });
    if (!res.ok) {
      const b = await res.json().catch(() => null);
      const d = b?.detail;
      throw new Error(
        Array.isArray(d) ? `${d[0]?.loc?.slice(1).join(".")} — ${d[0]?.msg}` : (d ?? "Please check the form."),
      );
    }
    const validated = await res.json();

    // Keep it against the account, not just this tab. Without this the form
    // exists only inside whichever session it was convened for, so "Your DAF"
    // has nothing to show and a closed tab loses the typing.
    if (!cameFromUpload) {
      // A failure here is not fatal — the draft still reaches the review step —
      // but it must be visible, because a silent catch is how "Your DAF" ends
      // up empty with nothing in the logs to say why.
      try {
        const saved = await authFetch("/api/me/daf", {
          method: "PUT",
          body: JSON.stringify({ form: nextForm, daf: validated?.daf ?? null }),
        });
        if (!saved.ok && saved.status !== 401) {
          console.warn("Your form was not saved to your account", saved.status);
        }
      } catch (err) {
        console.warn("Your form was not saved to your account", err);
      }
    }

    stashDafDraft({ form: nextForm, fromUpload: cameFromUpload, rawFields });
    router.push("/daf/review");
  }

  /** Read a scanned DAF and fill in whatever it could make out. */
  async function onUpload(file: File) {
    setUploading(true);
    setUploadPhase("sending");
    setUploadPct(0);
    setUploadName(file.name);
    setError(null);
    setUploadNote(null);
    try {
      const body = new FormData();
      body.append("file", file);

      interface UploadReply {
        daf?: Record<string, unknown>;
        missing?: string[];
        complete?: boolean;
        fields_read?: number;
        raw_fields?: Record<string, string>;
        error?: string;
      }

      const res = await authUpload<UploadReply>(
        "/api/daf/upload",
        body,
        (fraction) => {
          setUploadPct(Math.round(fraction * 100));
          // Once the bytes are gone there is nothing left to measure.
          if (fraction >= 1) setUploadPhase("reading");
        },
      );
      const data: UploadReply = res.data ?? {};
      if (!res.ok) throw new Error(data.error ?? "That form could not be read.");

      setForm((prev) => ({ ...prev, ...formFromUpload(data.daf ?? {}) }));

      setFromUpload(true);
      setMissing(data.missing ?? []);
      setUploadNote(
        data.complete
          ? `Read ${data.fields_read} fields from your form.`
          : `Read ${data.fields_read} fields. The rest are only on DAF-II — add them below.`,
      );

      // Both sources land on the same review step. A complete upload goes
      // straight there; an incomplete one stops so the gaps can be filled
      // first, because the board cannot question on what it was never given.
      // An upload always goes to review. The flow is the same whichever way
      // the material arrived — only the input differs. Anything DAF-I could
      // not supply is carried through and flagged there, not used to block
      // the aspirant on this page.
      await review({ ...form, ...formFromUpload(data.daf ?? {}) }, true, data.raw_fields);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That file could not be read.");
    } finally {
      setUploading(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await review(form, fromUpload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  }


  return (
    <>
      <AppHeader />
      <main className="mx-auto w-full max-w-[1100px] flex-1 px-6 py-12 sm:px-10">
        <h1 className="text-[32px] font-bold tracking-[-0.03em]">Your application form</h1>
        <p className="mt-2 max-w-2xl text-[16px] leading-relaxed text-ink-soft">
          The board questions from this and nothing else. What you leave thin
          here, they will find.
        </p>

        {/* --- Upload --- */}
        <div className="card mt-8 flex flex-wrap items-center gap-5 p-6">
          <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-accent-wash">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
                 className="text-accent" aria-hidden>
              <path d="M12 16V4M8 8l4-4 4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
            </svg>
          </span>

          <div className="min-w-[16rem] flex-1">
            <p className="text-[16px] font-semibold">Upload your DAF as a PDF</p>
            <p className="mt-1 text-[14px] leading-relaxed text-ink-soft">
              Scanned forms are fine — we read them. Everything it finds is filled
              in below for you to check.
            </p>
          </div>

          <input
            ref={fileRef}
            type="file"
            accept="application/pdf"
            data-testid="daf-file"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onUpload(f);
            }}
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            data-testid="daf-upload"
            className="rounded-full bg-accent px-6 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-accent-deep disabled:opacity-60"
          >
            {uploading ? "Reading your form…" : "Choose PDF"}
          </button>
        </div>

        {uploading && (
          <DafUploadProgress phase={uploadPhase} pct={uploadPct} fileName={uploadName} />
        )}

        {uploadNote && (
          <p data-testid="upload-note" className="mt-4 rounded-xl bg-accent-wash px-5 py-3.5 text-[14px] text-accent-deep">
            {uploadNote}
            {missing.length > 0 && (
              <span className="mt-1 block font-medium">Still needed: {missing.join(", ")}</span>
            )}
          </p>
        )}

        <p className="mt-8 text-[14px] text-ink-faint">Or fill it in yourself —</p>

        {/* --- The form --- */}
        <form onSubmit={onSubmit} data-testid="daf-form" className="mt-4 space-y-4">
          {SECTIONS.map((section) => (
            <section key={section.title} className="card p-6 sm:p-8">
              <h2 className="text-[19px] font-semibold">{section.title}</h2>
              <p className="mt-1 text-[14px] leading-relaxed text-ink-soft">{section.hint}</p>

              <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {section.fields.map((f) => (
                  <label key={f.key} className={`block ${f.wide ? "sm:col-span-2 lg:col-span-3" : ""}`}>
                    <span className="flex items-baseline gap-2">
                      <span className="text-[13px] font-medium text-ink">{f.label}</span>
                      {!REQUIRED.has(f.key) && (
                        <span className="text-[12px] text-ink-faint">Optional</span>
                      )}
                    </span>
                    <input
                      required={REQUIRED.has(f.key)}
                      name={f.key}
                      value={form[f.key] ?? ""}
                      onChange={set(f.key)}
                      placeholder={f.placeholder}
                      className={inputClass}
                    />
                    {f.note && (
                      <span className="mt-1.5 block text-[12px] leading-relaxed text-ink-soft">
                        {f.note}
                      </span>
                    )}
                  </label>
                ))}
              </div>
            </section>
          ))}

          {error && (
            <p role="alert" data-testid="daf-error"
               className="rounded-xl bg-danger-wash px-5 py-3.5 text-[14px] text-danger">
              {error}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-5 pt-2">
            <button
              type="submit"
              disabled={submitting}
              data-testid="daf-submit"
              className="rounded-full bg-accent px-8 py-3.5 text-[15px] font-semibold text-white transition-colors hover:bg-accent-deep disabled:opacity-50"
            >
              {submitting ? "Checking…" : "Review my form"}
            </button>
            <button
              type="button"
              onClick={() => setForm(SPECIMEN)}
              data-testid="daf-specimen"
              className="text-[14px] font-semibold text-accent hover:underline"
            >
              Fill with a sample
            </button>
          </div>
        </form>

      </main>
      <SiteFooter />
    </>
  );
}
