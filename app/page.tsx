import Image from "next/image";
import Link from "next/link";
import heroBoard from "@/public/hero-board.png";
import { AppHeader } from "@/components/AppHeader";
import { FaqSection } from "@/components/FaqSection";
import { ResumeMock } from "@/components/ResumeMock";
import { SiteFooter } from "@/components/SiteFooter";
import { Testimonials } from "@/components/Testimonials";
import {
  IconBoard,
  IconChart,
  IconClock,
  IconForm,
  IconMic,
  IconShield,
  IconTarget,
} from "@/components/Icons";

export const dynamic = "force-dynamic";

/**
 * Landing page.
 *
 * Sells the outcome, not the machinery. An aspirant does not care how many
 * agents there are or what the members are called — they care whether they
 * will freeze in the room, and what it will cost them. Everything here is
 * written from that side of the table.
 */

const ASSURANCES = [
  { Icon: IconBoard, label: "Five-member board" },
  { Icon: IconShield, label: "Never praises you" },
  { Icon: IconChart, label: "Marks in minutes" },
];

const FEARS = [
  {
    Icon: IconMic,
    fear: "“I freeze when they cut me off.”",
    answer:
      "Your board interrupts. If you run long or drift, they stop you mid-sentence — the same way the real one will. You practise recovering, not reciting.",
  },
  {
    Icon: IconShield,
    fear: "“I don’t know when I’m bluffing.”",
    answer:
      "Say something you are not sure of and a member challenges it on the spot. Afterwards you are shown every claim you defended, corrected, or abandoned.",
  },
  {
    Icon: IconTarget,
    fear: "“Mocks feel too easy and too kind.”",
    answer:
      "This one never praises you. No encouragement, no hints, no softening. A flat “Hmm” and the next question, until they find where your depth ends.",
  },
  {
    Icon: IconChart,
    fear: "“I get feedback, but not what to fix.”",
    answer:
      "Not a grade. The exact moments that cost you marks, quoted back in your own words, and what to practise before you face the real board.",
  },
];

const STEPS = [
  {
    n: "01",
    Icon: IconForm,
    title: "Give them your DAF",
    body: "Home district, optional subject, hobbies, service preference. Three minutes.",
  },
  {
    n: "02",
    Icon: IconClock,
    title: "They prepare",
    body: "Your board reads the form and builds its own questioning before you walk in.",
  },
  {
    n: "03",
    Icon: IconMic,
    title: "Sit the interview",
    body: "Half an hour, spoken aloud. Answer the way you would at Dholpur House.",
  },
  {
    n: "04",
    Icon: IconChart,
    title: "Face the marks",
    body: "Where you lost them, why, and what to do about it before the next attempt.",
  },
];

export default async function Home() {
  return (
    <>
      <AppHeader transparentUntilScrolled />

      <main className="flex-1">
        {/* ================= Hero ================= */}
        <section className="relative overflow-hidden">
          {/* Light wash behind the hero so the floating nav has something to
              lift off, without introducing a hard band. */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(120%_90%_at_82%_8%,var(--color-accent-wash)_0%,transparent_58%)]"
          />

          <div className="relative mx-auto grid w-full max-w-[1400px] items-center gap-16 px-6 pt-32 pb-24 sm:px-10 lg:grid-cols-[1.05fr_0.95fr] lg:pt-40 lg:pb-28">
            <div>
              <span className="animate-rise inline-flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2 text-[13px] font-semibold text-accent shadow-card">
                <IconClock className="size-4" />
                For the UPSC Civil Services Personality Test
              </span>

              <h1
                className="animate-rise mt-7 text-[clamp(2.6rem,5.2vw,4.3rem)] leading-[1.04] font-bold tracking-[-0.035em] text-balance"
                style={{ animationDelay: "60ms" }}
              >
                Two hundred marks are decided in{" "}
                <span className="relative whitespace-nowrap">
                  half an hour.
                  <svg
                    aria-hidden
                    viewBox="0 0 240 12"
                    preserveAspectRatio="none"
                    className="absolute -bottom-1 left-0 h-[10px] w-full text-brass"
                  >
                    <path
                      d="M2 8c40-6 92-7 138-4 34 2 66 5 98 2"
                      stroke="currentColor"
                      strokeWidth="3.5"
                      strokeLinecap="round"
                      fill="none"
                    />
                  </svg>
                </span>
              </h1>

              <p
                className="animate-rise mt-8 max-w-xl text-[18px] leading-[1.65] text-ink-soft"
                style={{ animationDelay: "120ms" }}
              >
                You have prepared for years. The interview is the one paper you
                cannot revise for alone — and the only one where a panel decides
                whether you are fit to serve. Sit it before it counts.
              </p>

              <div
                className="animate-rise mt-9 flex flex-wrap items-center gap-3"
                style={{ animationDelay: "180ms" }}
              >
                <Link
                  href="/daf"
                  data-testid="cta-daf"
                  className="rounded-full bg-accent px-8 py-4 text-[16px] font-semibold text-white transition-colors hover:bg-accent-deep"
                >
                  Sit a mock interview
                </Link>
                <Link
                  href="/mocks"
                  className="rounded-full border border-line-strong bg-surface px-8 py-4 text-[16px] font-semibold text-ink transition-colors hover:bg-surface-sunk"
                >
                  My attempts
                </Link>
              </div>

              {/* Entry point. Becomes a resume prompt when the aspirant has
                  an attempt they never finished. */}
              <div className="animate-rise mt-6" style={{ animationDelay: "220ms" }}>
                <ResumeMock />
              </div>

              <ul
                className="animate-rise mt-7 flex flex-wrap items-center gap-x-7 gap-y-3"
                style={{ animationDelay: "260ms" }}
              >
                {ASSURANCES.map(({ Icon, label }) => (
                  <li key={label} className="flex items-center gap-2 text-[14px] text-ink-soft">
                    <Icon className="size-4 text-brass" />
                    {label}
                  </li>
                ))}
              </ul>
            </div>

            {/* --- The room, with the numbers that matter floating off it --- */}
            <div className="animate-rise relative" style={{ animationDelay: "300ms" }}>
              {/* An explicit ratio rather than h-full: the grid row's height is
                  content-derived, so percentage heights inside it never
                  resolve. The ratio is taller than the file's native 1.64:1,
                  so object-cover trims the flanks and gives the room presence. */}
              <div className="relative aspect-[16/11] overflow-hidden rounded-3xl border border-line shadow-lift lg:aspect-[7/6]">
                {/* The hero is the LCP element: `priority` preloads it and the
                    blur placeholder covers the decode, so the slot never
                    collapses. Static import means Next knows the intrinsic
                    size and emits AVIF/WebP at the widths actually used. */}
                <Image
                  src={heroBoard}
                  alt="An empty UPSC interview board — five chairs behind the table, one facing them"
                  fill
                  priority
                  placeholder="blur"
                  sizes="(min-width: 1024px) 620px, 100vw"
                  // Crops the flanks rather than squashing the room, and sits
                  // slightly high so the empty chair stays in frame.
                  className="select-none object-cover object-[center_40%]"
                  draggable={false}
                />
              </div>

              <div className="absolute -bottom-6 -left-4 flex items-center gap-3 rounded-2xl border border-line bg-surface px-5 py-4 shadow-pop sm:-left-8">
                <span className="grid size-11 place-items-center rounded-full bg-accent-wash text-accent">
                  <IconBoard className="size-5" />
                </span>
                <span>
                  <span className="block text-[20px] leading-none font-bold text-ink tabular-nums">
                    5
                  </span>
                  <span className="mt-1 block text-[13px] text-ink-soft">
                    independent scorecards
                  </span>
                </span>
              </div>

              <div className="absolute -top-5 -right-3 rounded-2xl border border-line bg-surface px-5 py-3.5 shadow-pop sm:-right-6">
                <span className="block text-[20px] leading-none font-bold text-ink tabular-nums">
                  275
                </span>
                <span className="mt-1 block text-[13px] text-ink-soft">marks, scored</span>
              </div>
            </div>
          </div>
        </section>

        {/* ================= What it tests ================= */}
        <section id="fears" className="scroll-mt-28 border-y border-line bg-surface">
          <div className="mx-auto w-full max-w-[1400px] px-6 py-24 sm:px-10">
            <div className="max-w-2xl">
              <h2 className="text-[clamp(1.9rem,3vw,2.6rem)] font-bold tracking-[-0.03em]">
                Nobody fails this paper on knowledge
              </h2>
              <p className="mt-4 text-[17px] leading-[1.7] text-ink-soft">
                You cleared Mains on knowledge. Marks go on judgement, on
                structure, and on what you do when you are caught not knowing
                something. Those cannot be practised from notes.
              </p>
            </div>

            <ul className="mt-14 grid gap-6 lg:grid-cols-2">
              {FEARS.map(({ Icon, fear, answer }) => (
                <li key={fear} className="card p-8">
                  <span className="grid size-11 place-items-center rounded-xl bg-accent-wash text-accent">
                    <Icon />
                  </span>
                  <p className="mt-5 text-[19px] font-semibold text-ink">{fear}</p>
                  <p className="mt-3 text-[15px] leading-[1.7] text-ink-soft">{answer}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ================= Numbers ================= */}
        <section className="bg-accent text-white">
          <div className="mx-auto grid w-full max-w-[1400px] gap-12 px-6 py-20 sm:px-10 sm:grid-cols-3">
            {[
              ["5", "Members on your board", "A Chairman and four experts"],
              ["275", "Marks, the official ceiling", "Scored the way the board scores"],
              ["7", "Traits assessed", "The rubric UPSC publishes"],
            ].map(([value, label, sub]) => (
              <div key={label} className="text-center sm:text-left">
                <p className="font-display text-[clamp(2.8rem,5vw,4rem)] leading-none font-bold text-brass-bright tabular-nums">
                  {value}
                </p>
                <p className="mt-4 text-[17px] font-semibold">{label}</p>
                <p className="mt-1 text-[14px] text-white/60">{sub}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ================= How ================= */}
        <section id="how" className="scroll-mt-28">
          <div className="mx-auto w-full max-w-[1400px] px-6 py-24 sm:px-10">
            <h2 className="text-[clamp(1.9rem,3vw,2.6rem)] font-bold tracking-[-0.03em]">
              From your form to your marks
            </h2>

            <ol className="mt-14 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map(({ n, Icon, title, body }) => (
                <li key={n}>
                  <span className="flex items-center gap-3">
                    <span className="grid size-11 place-items-center rounded-xl border border-line bg-surface text-accent">
                      <Icon className="size-5" />
                    </span>
                    <span className="font-mono text-[13px] font-medium text-ink-faint">
                      {n}
                    </span>
                  </span>
                  <h3 className="mt-5 text-[18px] font-semibold">{title}</h3>
                  <p className="mt-2 text-[15px] leading-[1.7] text-ink-soft">{body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ================= Proof ================= */}
        <Testimonials />

        {/* ================= FAQ ================= */}
        <FaqSection />

        {/* ================= Closing ================= */}
        <section className="mx-auto w-full max-w-[1400px] px-6 pb-24 sm:px-10">
          <div className="rounded-3xl border border-line bg-surface px-8 py-20 text-center shadow-card sm:px-16">
            <h2 className="mx-auto max-w-3xl text-[clamp(1.9rem,3.6vw,2.8rem)] leading-[1.15] font-bold tracking-[-0.03em] text-balance">
              Better to be caught out here than in there.
            </h2>
            <p className="mx-auto mt-5 max-w-xl text-[17px] leading-relaxed text-ink-soft">
              Half an hour now, against a board that will not go easy on you.
            </p>
            <Link
              href="/daf"
              className="mt-9 inline-block rounded-full bg-accent px-8 py-4 text-[16px] font-semibold text-white transition-colors hover:bg-accent-deep"
            >
              Sit a mock interview
            </Link>
          </div>
        </section>
      </main>

      <SiteFooter />
    </>
  );
}
