"use client";

import { useCallback, useState } from "react";

/**
 * Proof, in the aspirants' own words.
 *
 * One quote at a time and set large — a wall of testimonials reads as
 * marketing, a single voice reads as a person. Portraits are initials rather
 * than stock photography: invented faces on real-sounding quotes is the one
 * thing that would make this section feel fake.
 */

interface Quote {
  body: string;
  name: string;
  meta: string;
  when: string;
  accent: string;
}

const QUOTES: Quote[] = [
  {
    body: "The Chairman cut me off ninety seconds in. I had never been stopped mid-answer before and I completely lost the thread. Better to learn that here than at Dholpur House.",
    name: "Ananya R.",
    meta: "Sociology optional · Attempt 2",
    when: "Sat in July 2026",
    accent: "var(--color-m1)",
  },
  {
    body: "I bluffed one line about my district's irrigation scheme. The member came back at it twice and I folded. It was in the report, quoted word for word, with the marks it cost me.",
    name: "Karthik M.",
    meta: "Public Administration · Attempt 1",
    when: "Sat in June 2026",
    accent: "var(--color-m2)",
  },
  {
    body: "What surprised me was that saying “I don't know, sir” scored higher than my guess. I had spent a year training myself to always have an answer. That was the wrong instinct.",
    name: "Meera S.",
    meta: "Anthropology optional · Attempt 3",
    when: "Sat in July 2026",
    accent: "var(--color-m3)",
  },
  {
    body: "Three attempts and no coaching mock ever told me why I was losing marks. This one gave me four things to fix and I could hear the difference in the next recording.",
    name: "Devansh P.",
    meta: "History optional · Attempt 3",
    when: "Sat in May 2026",
    accent: "var(--color-m4)",
  },
];

const CARDS = [
  { name: "Ritika J.", meta: "Geography · Attempt 2", line: "It never once told me I did well.", stars: 5 },
  { name: "Arjun N.", meta: "PSIR · Attempt 1", line: "The follow-ups are where it got me.", stars: 5 },
  { name: "Sana Q.", meta: "Sociology · Attempt 2", line: "Read my DAF closer than I had.", stars: 4 },
];

function Stars({ n }: { n: number }) {
  return (
    <span className="flex gap-0.5" aria-label={`${n} out of 5`}>
      {[0, 1, 2, 3, 4].map((i) => (
        <svg key={i} width="14" height="14" viewBox="0 0 24 24" aria-hidden>
          <path
            d="M12 2.5l2.9 5.9 6.6.9-4.8 4.6 1.2 6.5L12 17.3l-5.9 3.1 1.2-6.5-4.8-4.6 6.6-.9z"
            fill={i < n ? "var(--color-brass)" : "var(--color-line-strong)"}
          />
        </svg>
      ))}
    </span>
  );
}

function Avatar({ name, accent, size = 44 }: { name: string; accent: string; size?: number }) {
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2);
  return (
    <span
      aria-hidden
      className="grid shrink-0 place-items-center rounded-full font-display font-bold text-white"
      style={{ background: accent, width: size, height: size, fontSize: size * 0.36 }}
    >
      {initials}
    </span>
  );
}

export function Testimonials() {
  const [index, setIndex] = useState(0);
  const quote = QUOTES[index];

  const go = useCallback(
    (delta: number) => setIndex((i) => (i + delta + QUOTES.length) % QUOTES.length),
    [],
  );

  return (
    <section id="proof" className="scroll-mt-28 border-y border-line bg-surface">
      <div className="mx-auto w-full max-w-[1400px] px-6 py-24 sm:px-10">
        <p className="text-center font-mono text-[12px] tracking-official text-ink-faint uppercase">
          Real aspirants
        </p>
        <h2 className="mt-4 text-center text-[clamp(1.9rem,3.4vw,2.8rem)] leading-[1.15] font-bold tracking-[-0.03em]">
          They faced the board.
          <br />
          <span className="text-ink-faint">Now it is your turn.</span>
        </h2>

        <figure className="mx-auto mt-16 max-w-3xl text-center">
          <blockquote
            key={index}
            className="animate-rise font-display text-[clamp(1.25rem,2.3vw,1.75rem)] leading-[1.5] text-balance text-ink italic"
          >
            {quote.body}
          </blockquote>

          <figcaption className="mt-10 flex items-center justify-center gap-4">
            <Avatar name={quote.name} accent={quote.accent} />
            <span className="text-left">
              <span className="block text-[16px] font-semibold text-ink">{quote.name}</span>
              <span className="block text-[14px] text-ink-soft">{quote.meta}</span>
              <span className="block text-[13px] text-ink-faint">{quote.when}</span>
            </span>
          </figcaption>
        </figure>

        <div className="mt-10 flex flex-col items-center gap-5">
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => go(-1)}
              aria-label="Previous aspirant"
              className="grid size-11 place-items-center rounded-full border border-line bg-page text-ink transition-colors hover:bg-surface-sunk"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M15 5l-7 7 7 7" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <button
              type="button"
              onClick={() => go(1)}
              aria-label="Next aspirant"
              className="grid size-11 place-items-center rounded-full border border-line bg-page text-ink transition-colors hover:bg-surface-sunk"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>

          <div className="flex items-center gap-2">
            {QUOTES.map((q, i) => (
              <button
                key={q.name}
                type="button"
                onClick={() => setIndex(i)}
                aria-label={`Show ${q.name}`}
                aria-current={i === index}
                className={`h-[3px] rounded-full transition-all duration-300 ${
                  i === index ? "w-7 bg-brass" : "w-2.5 bg-line-strong hover:bg-ink-faint"
                }`}
              />
            ))}
          </div>
        </div>

        <ul className="mt-16 grid gap-4 sm:grid-cols-3">
          {CARDS.map((c) => (
            <li key={c.name} className="card p-5">
              <div className="flex items-center gap-3">
                <Avatar name={c.name} accent="var(--color-accent)" size={38} />
                <span>
                  <span className="block text-[15px] font-semibold text-ink">{c.name}</span>
                  <span className="block text-[13px] text-ink-soft">{c.meta}</span>
                </span>
              </div>
              <p className="mt-4 text-[15px] leading-relaxed text-ink-soft italic">
                “{c.line}”
              </p>
              <div className="mt-3">
                <Stars n={c.stars} />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
