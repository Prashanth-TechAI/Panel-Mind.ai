"use client";

import Link from "next/link";
import { useState } from "react";

/**
 * Questions, answered straight.
 *
 * Split layout: the ask sits on the left and stays put while the answers open
 * on the right, so the section never loses its anchor as rows expand. Only one
 * row is open at a time — a page of simultaneously open accordions is just a
 * wall of text with extra clicks.
 */

const FAQS = [
  {
    q: "How close is this to the real personality test?",
    a: "The format is faithful. A Chairman opens and roams, hands to one member at a time, each drills a single thread with short factual follow-ups until you run dry, then the Chairman closes. Questions come only from your DAF. What no simulator can replicate is the room itself — the walk in, the chairs, the silence.",
  },
  {
    q: "Are these real UPSC marks?",
    a: "No, and it says so on every scorecard. The score is calibrated to the range real boards award, but it is produced by an AI panel and is not affiliated with the Commission. Use it to measure yourself against your own last attempt, never to predict your result.",
  },
  {
    q: "What does this catch that a coaching mock does not?",
    a: "Bluffing, and the cost of it. A human panel may let a confident wrong answer pass. This one challenges the claim, records whether you doubled down or corrected yourself, and marks you on it — because integrity under pressure is what the board is actually testing.",
  },
  {
    q: "Is admitting I don’t know penalised?",
    a: "The opposite. Saying “I don’t know, sir” is scored as a positive; guessing to fill the silence is scored as a negative. That is how real boards treat it, and most aspirants have it backwards.",
  },
  {
    q: "How many times can I sit it?",
    a: "As often as you like. Each attempt is kept with its full transcript and marks, and your progress page shows whether you are actually improving or repeating the same mistakes.",
  },
  {
    q: "Do I need a microphone?",
    a: "Yes — the interview is spoken aloud in real time, the way the real one is. A laptop microphone is enough. Nothing is recorded to disk beyond the transcript that appears in your report.",
  },
];

const PREVIEW = 3;

export function FaqSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? FAQS : FAQS.slice(0, PREVIEW);

  return (
    <section id="faq" className="scroll-mt-28">
      <div className="mx-auto grid w-full max-w-[1400px] gap-14 px-6 py-24 sm:px-10 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="lg:sticky lg:top-28 lg:self-start">
          <h2 className="text-[clamp(2rem,3.4vw,2.8rem)] font-bold tracking-[-0.03em]">
            FAQ<span className="text-accent-bright">s</span>
          </h2>
          <p className="mt-4 max-w-sm text-[16px] leading-[1.7] text-ink-soft">
            What this is, what it is not, and what it can honestly tell you
            about where you stand.
          </p>
          <Link
            href="/contact"
            className="mt-8 inline-block rounded-full border border-line-strong px-7 py-3.5 text-[15px] font-semibold text-ink transition-colors hover:bg-surface-sunk"
          >
            Contact us
          </Link>
        </div>

        <div>
          <dl className="border-t border-line">
            {visible.map((item, i) => {
              const isOpen = openIndex === i;
              return (
                <div key={item.q} className="border-b border-line">
                  <dt>
                    <button
                      type="button"
                      onClick={() => setOpenIndex(isOpen ? null : i)}
                      aria-expanded={isOpen}
                      aria-controls={`faq-answer-${i}`}
                      className="flex w-full items-center justify-between gap-6 py-6 text-left"
                    >
                      <span className="flex gap-3 text-[17px] font-semibold text-ink">
                        <span className="text-ink-faint tabular-nums">{i + 1}.</span>
                        {item.q}
                      </span>
                      <span
                        aria-hidden
                        className={`grid size-8 shrink-0 place-items-center rounded-full text-ink-soft transition-all duration-200 ${
                          isOpen ? "rotate-180 bg-accent-wash text-accent" : ""
                        }`}
                      >
                        <svg width="13" height="8" viewBox="0 0 10 6" fill="none">
                          <path
                            d="M1 1l4 4 4-4"
                            stroke="currentColor"
                            strokeWidth="1.6"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </span>
                    </button>
                  </dt>
                  {/* Grid-rows trick animates to the content's natural height,
                      which max-height cannot do without a magic number. */}
                  <dd
                    id={`faq-answer-${i}`}
                    className={`grid transition-all duration-300 ease-out motion-reduce:transition-none ${
                      isOpen ? "grid-rows-[1fr] pb-7 opacity-100" : "grid-rows-[0fr] opacity-0"
                    }`}
                  >
                    <span className="overflow-hidden">
                      <span className="block max-w-2xl pr-12 text-[15px] leading-[1.75] text-ink-soft">
                        {item.a}
                      </span>
                    </span>
                  </dd>
                </div>
              );
            })}
          </dl>

          {!showAll && FAQS.length > PREVIEW && (
            <div className="mt-8 flex justify-end">
              <button
                type="button"
                onClick={() => setShowAll(true)}
                className="rounded-full border border-line-strong px-7 py-3 text-[15px] font-semibold text-ink transition-colors hover:bg-surface-sunk"
              >
                View more
              </button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
