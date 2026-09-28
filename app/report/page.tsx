"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { SiteFooter } from "@/components/SiteFooter";
import { API_BASE } from "@/lib/api";

/**
 * The scorecard.
 *
 * Forms follow the data's job: the consolidated mark is a hero number, not a
 * chart; trait scores and per-member marks are magnitude, so they are bars.
 * A radar was rejected — it encodes by area and distorts exactly the
 * comparison a candidate needs to make.
 */

interface TraitScore {
  trait: string;
  score: number;
  note: string;
}

interface AnswerFlag {
  kind: "bluff" | "evasive" | "rambling" | "admitted_ignorance" | "one_sided" | "strong";
  quote: string;
  comment: string;
}

interface Scorecard {
  member_id: string;
  member_name: string;
  traits: TraitScore[];
  marks: number;
  remark: string;
  flags: AnswerFlag[];
}

interface Report {
  candidate: string;
  consolidated_marks: number;
  scorecards: Scorecard[];
  trait_averages: Record<string, number>;
  signals: {
    answers: number;
    total_words: number;
    average_words_per_answer: number;
    longest_answer_words: number;
    filler_ratio: number;
    admitted_ignorance_count: number;
    interruptions_taken: number;
  };
  summary: string;
  lost_marks: string[];
  improvements: { area: string; why: string; action: string }[];
  evaluators_failed: string[];
  calibration_note: string;
}

const MAX_MARKS = 275;

const TRAIT_LABELS: Record<string, string> = {
  mental_alertness: "Mental alertness",
  critical_assimilation: "Critical assimilation",
  clear_exposition: "Clear exposition",
  balance_of_judgement: "Balance of judgement",
  depth_of_interest: "Depth of interest",
  social_leadership: "Social cohesion & leadership",
  moral_integrity: "Moral integrity",
};

const MEMBER_ACCENT: Record<string, string> = {
  M0: "var(--color-m0)",
  M1: "var(--color-m1)",
  M2: "var(--color-m2)",
  M3: "var(--color-m3)",
  M4: "var(--color-m4)",
};

/** Flags are status, not series — reserved colours, always with a label. */
const FLAG_STYLE: Record<AnswerFlag["kind"], { label: string; color: string }> = {
  bluff: { label: "Bluffed", color: "var(--color-danger)" },
  evasive: { label: "Evasive", color: "var(--color-warn)" },
  rambling: { label: "Rambled", color: "var(--color-warn)" },
  one_sided: { label: "One-sided", color: "var(--color-warn)" },
  admitted_ignorance: { label: "Said “I don’t know”", color: "var(--color-good)" },
  strong: { label: "Strong", color: "var(--color-good)" },
};

function verdict(marks: number): string {
  if (marks >= 220) return "exceptional";
  if (marks >= 200) return "very strong";
  if (marks >= 175) return "good";
  if (marks >= 150) return "average";
  return "would not clear";
}

/** Horizontal bar. Thin mark, rounded data-end, anchored to the baseline. */
function Bar({
  value,
  max,
  color,
  label,
  readout,
}: {
  value: number;
  max: number;
  color: string;
  label: string;
  readout: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));

  return (
    <div className="grid grid-cols-[minmax(0,11rem)_1fr_auto] items-center gap-4">
      <span className="truncate text-[13px] text-ink/65">{label}</span>
      <span
        className="relative block h-2 rounded-full bg-ink/8"
        role="img"
        aria-label={`${label}: ${readout}`}
      >
        <span
          className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-1000 ease-out"
          style={{ width: `${pct}%`, background: color }}
        />
      </span>
      {/* Value wears a text token, never the series colour. */}
      <span className="font-mono text-[12px] tabular-nums text-ink/75">{readout}</span>
    </div>
  );
}

function ReportBody() {
  const params = useSearchParams();
  const sessionId = params.get("session");

  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showTable, setShowTable] = useState(false);

  const load = useCallback(async () => {
    if (!sessionId) {
      setError("No interview specified.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/evaluate`, {
        method: "POST",
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `Evaluation failed (${res.status})`);
      setReport(body as Report);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not fetch your marks.");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
    <AppHeader />
    <main className="mx-auto w-full max-w-[1200px] flex-1 px-6 py-12 sm:px-8">

      {loading && (
        <section
          data-testid="marking"
          className="flex flex-1 flex-col items-center justify-center py-32 text-center"
        >
          <h1 className="animate-rise text-[clamp(1.8rem,4vw,2.8rem)] font-bold">
            The board is marking you.
          </h1>
          <p className="animate-rise mt-4 text-[12px] font-medium text-ink-faint">
            five members are scoring independently · none sees the others
          </p>
        </section>
      )}

      {error && !loading && (
        <section className="py-24 text-center">
          <p
            data-testid="report-error"
            role="alert"
            className="mx-auto max-w-md border-l-2 border-danger bg-danger/5 px-5 py-3 text-left text-[13px] text-danger"
          >
            {error}
          </p>
          <button
            type="button"
            onClick={load}
            className="mt-8 cursor-pointer rounded-sm bg-ink px-6 py-3 text-[12px] font-medium text-page"
          >
            try again
          </button>
        </section>
      )}

      {report && !loading && (
        <div data-testid="report">
          {/* --- Hero number: not a chart --- */}
          <section className="mt-14 mb-20">
            <p className="text-[12px] font-medium text-brass">
              {report.candidate} · consolidated
            </p>
            <p className="mt-4 flex items-baseline gap-4">
              <span
                data-testid="consolidated-marks"
                className="text-[clamp(4rem,13vw,8rem)] leading-none font-bold tabular-nums"
              >
                {report.consolidated_marks}
              </span>
              <span className="text-3xl font-bold text-ink-faint">
                / {MAX_MARKS}
              </span>
            </p>
            <p className="mt-3 text-[12px] font-medium text-ink-soft">
              {verdict(report.consolidated_marks)} · mean of{" "}
              {report.scorecards.length} independent scorecards
            </p>
            <p className="mt-8 max-w-2xl text-[15px] leading-relaxed text-ink/75">
              {report.summary}
            </p>
          </section>

          {/* --- Per-member marks --- */}
          <section className="mb-20">
            <h2 className="mb-6 text-2xl font-bold">
              How each member marked you
            </h2>
            <div className="space-y-3">
              {report.scorecards.map((card) => (
                <Bar
                  key={card.member_id}
                  value={card.marks}
                  max={MAX_MARKS}
                  color={MEMBER_ACCENT[card.member_id]}
                  label={card.member_name}
                  readout={`${card.marks}`}
                />
              ))}
            </div>
            <p className="mt-5 text-[12px] font-medium text-ink-faint">
              spread{" "}
              {Math.max(...report.scorecards.map((c) => c.marks)) -
                Math.min(...report.scorecards.map((c) => c.marks))}{" "}
              marks · disagreement between members is information
            </p>
          </section>

          {/* --- Traits: one series, so no legend --- */}
          <section className="mb-20">
            <div className="mb-6 flex items-baseline justify-between gap-4">
              <h2 className="text-2xl font-bold">
                The seven traits UPSC assesses
              </h2>
              <button
                type="button"
                onClick={() => setShowTable((v) => !v)}
                className="cursor-pointer text-[12px] font-medium text-ink-faint uppercase underline underline-offset-4 hover:text-brass"
              >
                {showTable ? "show chart" : "show table"}
              </button>
            </div>

            {showTable ? (
              <table className="w-full text-left text-[13px]">
                <thead>
                  <tr className="border-b border-line text-[12px] font-medium text-ink-soft">
                    <th className="py-2">Trait</th>
                    <th className="py-2 text-right">Board average</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(report.trait_averages).map(([trait, score]) => (
                    <tr key={trait} className="border-b border-line">
                      <td className="py-2 text-ink/70">
                        {TRAIT_LABELS[trait] ?? trait}
                      </td>
                      <td className="py-2 text-right font-mono tabular-nums text-ink/80">
                        {score.toFixed(1)} / 10
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="space-y-3">
                {Object.entries(report.trait_averages).map(([trait, score]) => (
                  <Bar
                    key={trait}
                    value={score}
                    max={10}
                    color="var(--color-brass)"
                    label={TRAIT_LABELS[trait] ?? trait}
                    readout={score.toFixed(1)}
                  />
                ))}
              </div>
            )}
          </section>

          {/* --- Where you lost marks --- */}
          {report.lost_marks.length > 0 && (
            <section className="mb-20">
              <h2 className="mb-6 text-2xl font-bold">
                Where you lost marks
              </h2>
              <ol data-testid="lost-marks" className="space-y-4">
                {report.lost_marks.map((item, index) => (
                  <li key={index} className="flex gap-4">
                    <span className="text-[12px] font-medium text-danger/70 tabular-nums">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="text-[14px] leading-relaxed text-ink/70">
                      {item}
                    </span>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {/* --- Member remarks and flags --- */}
          <section className="mb-20">
            <h2 className="mb-6 text-2xl font-bold">
              What each member wrote
            </h2>
            <ul className="grid gap-3 sm:grid-cols-2">
              {report.scorecards.map((card) => (
                <li
                  key={card.member_id}
                  className="card p-5"
                  style={{ boxShadow: `inset 3px 0 0 ${MEMBER_ACCENT[card.member_id]}` }}
                >
                  <p className="flex items-baseline justify-between gap-3">
                    <span className="text-[17px] font-medium">
                      {card.member_name}
                    </span>
                    <span className="font-mono text-[12px] tabular-nums text-ink-soft">
                      {card.marks}/{MAX_MARKS}
                    </span>
                  </p>
                  <p className="mt-2.5 text-[13px] leading-relaxed text-ink/65">
                    {card.remark}
                  </p>
                  {card.flags.length > 0 && (
                    <ul className="mt-4 space-y-2.5">
                      {card.flags.map((flag, index) => (
                        <li key={index}>
                          <span
                            className="text-[12px] font-medium"
                            style={{ color: FLAG_STYLE[flag.kind]?.color }}
                          >
                            {FLAG_STYLE[flag.kind]?.label ?? flag.kind}
                          </span>
                          <p className="mt-0.5 border-l border-line pl-3 text-[12px] leading-snug text-ink-soft italic">
                            “{flag.quote}”
                          </p>
                          <p className="mt-1 pl-3 text-[12px] leading-snug text-ink-soft">
                            {flag.comment}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </section>

          {/* --- What to fix --- */}
          {report.improvements.length > 0 && (
            <section className="mb-20">
              <h2 className="mb-6 text-2xl font-bold">
                What to fix before the real board
              </h2>
              <ul data-testid="improvements" className="space-y-6">
                {report.improvements.map((item, index) => (
                  <li key={index} className="card p-5">
                    <p className="text-[17px]">{item.area}</p>
                    <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
                      {item.why}
                    </p>
                    <p className="mt-2 text-[13px] leading-relaxed text-brass/80">
                      {item.action}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* --- Measured facts --- */}
          <section className="mb-16">
            <h2 className="mb-6 text-2xl font-bold">How you spoke</h2>
            <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3">
              {[
                ["answers given", report.signals.answers],
                ["avg words / answer", report.signals.average_words_per_answer],
                ["longest answer", `${report.signals.longest_answer_words} words`],
                ["filler ratio", `${(report.signals.filler_ratio * 100).toFixed(1)}%`],
                ["said “I don’t know”", `${report.signals.admitted_ignorance_count}×`],
                ["board interrupted you", `${report.signals.interruptions_taken}×`],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt className="text-[12px] font-medium text-ink-faint">
                    {label}
                  </dt>
                  <dd className="mt-1 font-mono text-[18px] tabular-nums text-ink/80">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          <footer>
            <div className="rule-brass" />
            <p className="mt-6 max-w-2xl text-[12px] leading-relaxed text-ink-faint">
              {report.calibration_note}
            </p>
            {report.evaluators_failed.length > 0 && (
              <p className="mt-3 text-[12px] font-medium text-brass/60">
                {report.evaluators_failed.length} member(s) could not score · mark
                averaged over the rest
              </p>
            )}
          </footer>
        </div>
      )}
    </main>
    <SiteFooter />
    </>
  );
}

export default function ReportPage() {
  return (
    <Suspense fallback={null}>
      <ReportBody />
    </Suspense>
  );
}
