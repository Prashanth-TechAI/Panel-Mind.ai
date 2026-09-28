"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";

/**
 * Plans, with the unit economics shown.
 *
 * This product's whole argument is that it does not flatter you. Hiding what a
 * mock costs to run would sit badly against that, and an aspirant deciding
 * between this and a ₹3,000 coaching mock deserves to see why the number is
 * what it is. The breakdown is an estimate at current provider rates, and says
 * so — it is not a bill.
 */

/** Assumed shape of one 28-minute interview, used for every figure below. */
const ASSUMPTIONS = [
  "28 minutes in the room, about 20 question-and-answer exchanges",
  "Five members preparing question trees before you enter",
  "Five members marking the transcript independently afterwards",
];

interface CostLine {
  label: string;
  detail: string;
  inr: number;
}

/**
 * Per-interview cost estimate in ₹. Text-to-speech dominates: the board speaks
 * for most of the half hour, and speech is charged by the character.
 */
const COSTS: CostLine[] = [
  { label: "Text-to-speech", detail: "The board's five voices, ~13,000 characters", inr: 113 },
  { label: "Language models", detail: "Preparation, live questioning, and five scorecards", inr: 57 },
  { label: "Real-time audio", detail: "Carrying the conversation both ways", inr: 3 },
  { label: "Speech-to-text", detail: "Transcribing your answers as you speak", inr: 2 },
  { label: "Servers and database", detail: "Compute, storage and the record of the sitting", inr: 5 },
];

const TOTAL = COSTS.reduce((sum, c) => sum + c.inr, 0);

interface Plan {
  id: string;
  name: string;
  price: number | null;
  per: string;
  mocks: string;
  best?: boolean;
  features: string[];
}

const PLANS: Plan[] = [
  {
    id: "free",
    name: "Free",
    price: 0,
    per: "while in preview",
    mocks: "1 mock interview",
    features: [
      "The full five-member board",
      "Complete scorecard and transcript",
      "Every trait scored against the UPSC rubric",
    ],
  },
  {
    id: "single",
    name: "Single sitting",
    price: 599,
    per: "one mock",
    mocks: "1 mock interview",
    features: [
      "Everything in Free",
      "Kept in My mocks with its transcript",
      "No expiry — sit it when you are ready",
    ],
  },
  {
    id: "series",
    name: "Series",
    price: 2499,
    per: "₹500 a mock",
    mocks: "5 mock interviews",
    best: true,
    features: [
      "Everything in Single sitting",
      "Progress tracked across attempts",
      "Valid for twelve months",
    ],
  },
  {
    id: "full",
    name: "Full preparation",
    price: 5999,
    per: "₹400 a mock",
    mocks: "15 mock interviews",
    features: [
      "Everything in Series",
      "Practice plan rebuilt from your own scorecards",
      "Priority when the board is busy",
    ],
  },
];

const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export function PlanPricing() {
  const { account } = useAuth();
  const [showCosts, setShowCosts] = useState(false);
  const used = account?.mocks_taken ?? 0;

  return (
    <section>
      {/* --- Where you stand --- */}
      <div
        data-testid="current-plan"
        className="rounded-3xl border border-line bg-surface p-6 shadow-card sm:p-8"
      >
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div>
            <p className="font-mono text-[12px] tracking-official text-ink-faint uppercase">
              Your plan
            </p>
            <p className="mt-2 flex items-baseline gap-3">
              <span className="font-display text-[28px] leading-none font-bold text-ink">
                Free
              </span>
              <span className="rounded-full bg-good-wash px-3 py-1 text-[12px] font-semibold text-good">
                Active
              </span>
            </p>
            <p className="mt-2 text-[15px] text-ink-soft">
              {used === 0
                ? "You have one mock to use. Nothing is charged while the product is in preview."
                : `You have sat ${used} mock${used > 1 ? "s" : ""}. Nothing is charged while the product is in preview.`}
            </p>
          </div>

        </div>
      </div>

      {/* --- Plans --- */}
      <div id="plans" className="scroll-mt-28">
        <h2 className="mt-12 text-[clamp(1.6rem,2.6vw,2.1rem)] font-bold tracking-[-0.03em]">
          When preview ends
        </h2>
        <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
          A coaching mock interview costs ₹1,500 to ₹5,000 and needs a slot
          booked days ahead. These are the prices we intend to charge. Nothing
          is live yet, and no card is taken today.
        </p>

        <ul className="mt-8 grid gap-4 lg:grid-cols-4">
          {PLANS.map((p) => (
            <li
              key={p.id}
              data-testid={`plan-${p.id}`}
              className={`relative flex flex-col rounded-2xl border p-6 ${
                p.best
                  ? "border-brass bg-surface shadow-lift"
                  : "border-line bg-surface shadow-card"
              }`}
            >
              {p.best && (
                <span className="absolute -top-3 left-6 rounded-full bg-brass px-3 py-1 text-[11px] font-bold tracking-official text-white uppercase">
                  Most chosen
                </span>
              )}

              <p className="text-[15px] font-semibold text-ink">{p.name}</p>
              <p className="mt-3 flex items-baseline gap-1.5">
                <span className="font-display text-[30px] leading-none font-bold text-ink">
                  {p.price === 0 ? "Free" : inr(p.price ?? 0)}
                </span>
              </p>
              <p className="mt-1 text-[13px] text-ink-faint">{p.per}</p>
              <p className="mt-4 text-[14px] font-medium text-accent">{p.mocks}</p>

              <ul className="mt-4 flex-1 space-y-2.5">
                {p.features.map((f) => (
                  <li key={f} className="flex gap-2.5 text-[13px] leading-relaxed text-ink-soft">
                    <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-brass" />
                    {f}
                  </li>
                ))}
              </ul>

              <button
                type="button"
                disabled
                className="mt-6 w-full cursor-not-allowed rounded-full border border-line-strong px-5 py-2.5 text-[14px] font-semibold text-ink-faint"
              >
                {p.id === "free" ? "Your plan" : "Not yet available"}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {/* --- What it costs us --- */}
      <div className="mt-12 rounded-3xl border border-line bg-page p-6 sm:p-8">
        <button
          type="button"
          onClick={() => setShowCosts((v) => !v)}
          aria-expanded={showCosts}
          data-testid="cost-toggle"
          className="flex w-full items-center justify-between gap-4 text-left"
        >
          <span>
            <span className="block text-[17px] font-semibold text-ink">
              What one interview costs to run
            </span>
            <span className="mt-1 block text-[14px] text-ink-soft">
              About {inr(TOTAL)} per sitting. Here is where it goes.
            </span>
          </span>
          <span
            aria-hidden
            className={`grid size-8 shrink-0 place-items-center rounded-full text-ink-soft transition-transform ${
              showCosts ? "rotate-180" : ""
            }`}
          >
            <svg width="13" height="8" viewBox="0 0 10 6" fill="none">
              <path d="M1 1l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </button>

        {showCosts && (
          <div data-testid="cost-breakdown" className="animate-rise mt-7">
            <ul className="space-y-3">
              {COSTS.map((c) => (
                <li key={c.label} className="grid grid-cols-[1fr_auto] items-center gap-4">
                  <span className="min-w-0">
                    <span className="block text-[14px] font-medium text-ink">{c.label}</span>
                    <span className="block truncate text-[13px] text-ink-soft">{c.detail}</span>
                  </span>
                  <span className="flex items-center gap-3">
                    <span
                      className="hidden h-1.5 rounded-full bg-brass sm:block"
                      style={{ width: `${Math.max(6, (c.inr / TOTAL) * 160)}px` }}
                      aria-hidden
                    />
                    <span className="w-14 text-right font-mono text-[13px] tabular-nums text-ink">
                      {inr(c.inr)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>

            <div className="mt-5 flex items-center justify-between border-t border-line pt-4">
              <span className="text-[15px] font-semibold text-ink">Estimated total</span>
              <span className="font-mono text-[15px] font-semibold tabular-nums text-ink">
                {inr(TOTAL)}
              </span>
            </div>

            <div className="mt-6">
              <p className="text-[13px] font-medium text-ink">Assuming</p>
              <ul className="mt-2 space-y-1.5">
                {ASSUMPTIONS.map((a) => (
                  <li key={a} className="flex gap-2.5 text-[13px] leading-relaxed text-ink-soft">
                    <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-ink-faint" />
                    {a}
                  </li>
                ))}
              </ul>
            </div>

            <p className="mt-6 text-[12px] leading-relaxed text-ink-faint">
              An estimate, not a bill. Figures are converted from provider rate
              cards in US dollars and move with usage, model choice and the
              exchange rate. Speech is the largest line because the board talks
              for most of the half hour and text-to-speech is charged by the
              character.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
