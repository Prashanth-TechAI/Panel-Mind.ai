import Link from "next/link";

/**
 * Site footer.
 *
 * Deep navy so the page closes on a firm edge rather than fading out, and
 * because it is the one surface where the brand can hold the whole field.
 * Every link here resolves — a footer full of dead ends is worse than a
 * short one.
 */

const COLUMNS: { title: string; links: { href: string; label: string }[] }[] = [
  {
    title: "Practice",
    links: [
      { href: "/daf", label: "Sit a mock interview" },
      { href: "/mocks", label: "My mocks" },
      { href: "/progress", label: "My progress" },
      { href: "/plan", label: "My plan" },
    ],
  },
  {
    title: "How it works",
    links: [
      { href: "/#how", label: "The format" },
      { href: "/#fears", label: "What it tests" },
      { href: "/#proof", label: "Real aspirants" },
      { href: "/#faq", label: "Questions" },
    ],
  },
  {
    title: "Support",
    links: [
      { href: "/contact", label: "Contact us" },
      { href: "/contact#help", label: "Help & support" },
      { href: "/signin", label: "Sign in" },
    ],
  },
  {
    title: "Policies",
    links: [
      { href: "/privacy", label: "Privacy Policy" },
      { href: "/terms", label: "Terms & Conditions" },
      { href: "/refunds", label: "Refunds & Cancellations" },
      { href: "/disclaimer", label: "Disclaimer" },
    ],
  },
];

const SOCIALS = [
  { label: "Instagram", href: "https://instagram.com" },
  { label: "X.com", href: "https://x.com" },
  { label: "LinkedIn", href: "https://linkedin.com" },
  { label: "YouTube", href: "https://youtube.com" },
];

function IconMail() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="1.7" />
      <path d="M3 7l9 6 9-6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

function IconPhone() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a1 1 0 01-1 1A16 16 0 014 5a1 1 0 011-1z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-4 rounded-t-[2.5rem] bg-accent text-white">
      <div className="mx-auto w-full max-w-[1400px] px-6 py-20 sm:px-10">
        <div className="grid gap-x-8 gap-y-14 sm:grid-cols-2 lg:grid-cols-[1.15fr_repeat(4,0.72fr)_0.55fr]">
          {/* --- Identity --- */}
          <div>
            <div className="flex items-center gap-2.5">
              {/* The mark is navy, so it sits on its own light chip here
                  rather than being recoloured into a different logo. */}
              <span className="grid h-12 place-items-center rounded-xl bg-white px-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/logo-mark.svg" alt="" width={44} height={36} className="h-9 w-auto" />
              </span>
              <span className="font-display text-[21px] leading-none font-bold tracking-[-0.015em] text-white">
                PanelMind <span className="text-brass-bright">AI</span>
              </span>
            </div>

            <p className="mt-6 max-w-xs text-[14px] leading-[1.7] text-white/60">
              Mock interviews for the UPSC Civil Services Personality Test.
              A five-member board that questions from your DAF and marks you
              the way the real one does.
            </p>

            <ul className="mt-7 space-y-3 text-[14px]">
              <li>
                <a
                  href="mailto:hello@panelmind.ai"
                  className="flex items-center gap-3 text-white/75 transition-colors hover:text-white"
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/10">
                    <IconMail />
                  </span>
                  hello@panelmind.ai
                </a>
              </li>
              <li>
                <a
                  href="tel:+919000000000"
                  className="flex items-center gap-3 text-white/75 transition-colors hover:text-white"
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/10">
                    <IconPhone />
                  </span>
                  +91 90000 00000
                </a>
              </li>
            </ul>
          </div>

          {/* --- Link columns --- */}
          {COLUMNS.map((col) => (
            <div key={col.title}>
              <h3 className="font-display text-[16px] font-bold text-white">{col.title}</h3>
              <ul className="mt-5 space-y-3">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <Link
                      href={l.href}
                      className="text-[14px] text-white/60 transition-colors hover:text-white"
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          {/* --- Socials --- */}
          <div>
            <h3 className="font-display text-[16px] font-bold text-white">Socials</h3>
            <ul className="mt-5 space-y-3">
              {SOCIALS.map((s) => (
                <li key={s.label}>
                  <a
                    href={s.href}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-[14px] text-white/60 transition-colors hover:text-white"
                  >
                    {s.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-16 flex flex-wrap items-center justify-between gap-4 border-t border-white/15 pt-8 text-[13px] text-white/50">
          <p>© {new Date().getFullYear()} PanelMind AI. All rights reserved.</p>
          <p className="max-w-xl">
            An independent preparation tool. Marks are indicative, produced by an
            AI panel, and are not affiliated with or endorsed by the Union Public
            Service Commission.
          </p>
        </div>
      </div>
    </footer>
  );
}
