import Link from "next/link";
import { AppHeader } from "@/components/AppHeader";
import { SiteFooter } from "@/components/SiteFooter";

/**
 * Shared shell for policy pages.
 *
 * Narrow measure and plain language on purpose: a policy nobody can read is a
 * policy nobody agreed to. Each page supplies only its own sections.
 */

export interface LegalSection {
  heading: string;
  body: string[];
  list?: string[];
}

export const POLICY_NAV = [
  { href: "/privacy", label: "Privacy Policy" },
  { href: "/terms", label: "Terms & Conditions" },
  { href: "/refunds", label: "Refunds & Cancellations" },
  { href: "/disclaimer", label: "Disclaimer" },
];

export function LegalPage({
  title,
  updated,
  intro,
  sections,
  current,
}: {
  title: string;
  updated: string;
  intro: string;
  sections: LegalSection[];
  current: string;
}) {
  return (
    <>
      <AppHeader />

      <main className="flex-1">
        <div className="mx-auto w-full max-w-[1400px] px-6 py-16 sm:px-10">
          <div className="grid gap-14 lg:grid-cols-[0.3fr_0.7fr]">
            {/* --- Sibling policies stay reachable from every policy --- */}
            <aside className="lg:sticky lg:top-28 lg:self-start">
              <p className="font-mono text-[12px] tracking-official text-ink-faint uppercase">
                Policies
              </p>
              <ul className="mt-5 space-y-1">
                {POLICY_NAV.map((p) => {
                  const active = p.href === current;
                  return (
                    <li key={p.href}>
                      <Link
                        href={p.href}
                        aria-current={active ? "page" : undefined}
                        className={`block rounded-lg px-3 py-2 text-[15px] transition-colors ${
                          active
                            ? "bg-accent-wash font-semibold text-accent"
                            : "text-ink-soft hover:bg-surface-sunk hover:text-ink"
                        }`}
                      >
                        {p.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>

              <div className="mt-8 rounded-2xl border border-line bg-surface p-5">
                <p className="text-[14px] font-semibold text-ink">Questions?</p>
                <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
                  Write to us and a person will answer.
                </p>
                <a
                  href="mailto:hello@panelmind.ai"
                  className="mt-3 inline-block text-[14px] font-semibold text-accent-bright hover:underline"
                >
                  hello@panelmind.ai
                </a>
              </div>
            </aside>

            <article className="max-w-2xl">
              <h1 className="text-[clamp(2rem,3.6vw,2.8rem)] leading-[1.1] font-bold tracking-[-0.03em]">
                {title}
              </h1>
              <p className="mt-3 font-mono text-[12px] tracking-official text-ink-faint uppercase">
                Last updated {updated}
              </p>
              <p className="mt-7 text-[17px] leading-[1.75] text-ink-soft">{intro}</p>

              <div className="mt-12 space-y-11">
                {sections.map((s) => (
                  <section key={s.heading}>
                    <h2 className="text-[20px] font-bold tracking-[-0.02em]">
                      {s.heading}
                    </h2>
                    {s.body.map((p) => (
                      <p key={p} className="mt-3 text-[15px] leading-[1.8] text-ink-soft">
                        {p}
                      </p>
                    ))}
                    {s.list && (
                      <ul className="mt-4 space-y-2.5">
                        {s.list.map((li) => (
                          <li
                            key={li}
                            className="flex gap-3 text-[15px] leading-[1.7] text-ink-soft"
                          >
                            <span
                              aria-hidden
                              className="mt-2.5 size-1.5 shrink-0 rounded-full bg-brass"
                            />
                            <span>{li}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>
                ))}
              </div>

              <div className="rule-brass mt-14" />
              <p className="mt-6 text-[13px] leading-relaxed text-ink-faint">
                PanelMind AI is an independent preparation tool. It is not
                affiliated with, endorsed by, or connected to the Union Public
                Service Commission or any government body.
              </p>
            </article>
          </div>
        </div>
      </main>

      <SiteFooter />
    </>
  );
}
