import type { Metadata } from "next";
import { AppHeader } from "@/components/AppHeader";
import { SiteFooter } from "@/components/SiteFooter";
import { IconClock, IconForm, IconShield } from "@/components/Icons";

export const metadata: Metadata = {
  title: "Contact — PanelMind AI",
  description:
    "Reach the PanelMind AI team about your mock interview, your marks, or anything that went wrong.",
};

/**
 * Contact.
 *
 * No form. A form here would promise a queue we do not yet run — direct
 * channels are honest and get a faster answer.
 */

const CHANNELS = [
  {
    Icon: IconForm,
    label: "Email",
    value: "hello@panelmind.ai",
    href: "mailto:hello@panelmind.ai",
    note: "Best for anything about your marks or a report that looks wrong.",
  },
  {
    Icon: IconClock,
    label: "WhatsApp",
    value: "+91 90000 00000",
    href: "https://wa.me/919000000000",
    note: "Quickest for a question before you sit your first mock.",
  },
  {
    Icon: IconShield,
    label: "Something broke mid-interview",
    value: "support@panelmind.ai",
    href: "mailto:support@panelmind.ai",
    note: "Send the time and your session link — nothing is lost, we can re-mark it.",
  },
];

export default function ContactPage() {
  return (
    <>
      <AppHeader />

      <main className="flex-1">
        <section className="mx-auto w-full max-w-[1400px] px-6 py-20 sm:px-10">
          <div className="max-w-2xl">
            <h1 className="text-[clamp(2.2rem,4vw,3.2rem)] leading-[1.1] font-bold tracking-[-0.03em]">
              Talk to a person
            </h1>
            <p className="mt-5 text-[17px] leading-[1.7] text-ink-soft">
              Real replies, usually the same day. If a board misbehaved or a
              scorecard looks wrong, say so — we would rather hear it than have
              you quietly stop practising.
            </p>
          </div>

          <ul className="mt-14 grid gap-5 lg:grid-cols-3">
            {CHANNELS.map(({ Icon, label, value, href, note }) => (
              <li key={label}>
                <a
                  href={href}
                  className="card flex h-full flex-col p-7 transition-shadow hover:shadow-lift"
                >
                  <span className="grid size-11 place-items-center rounded-xl bg-accent-wash text-accent">
                    <Icon className="size-5" />
                  </span>
                  <span className="mt-5 block text-[14px] font-medium text-ink-soft">
                    {label}
                  </span>
                  <span className="mt-1 block text-[18px] font-semibold text-ink">
                    {value}
                  </span>
                  <span className="mt-3 block text-[14px] leading-[1.7] text-ink-soft">
                    {note}
                  </span>
                </a>
              </li>
            ))}
          </ul>

          <div id="help" className="scroll-mt-28 mt-16 rounded-3xl border border-line bg-surface p-8 shadow-card sm:p-12">
            <h2 className="text-[24px] font-bold tracking-[-0.02em]">
              Before you write in
            </h2>
            <dl className="mt-8 grid gap-8 sm:grid-cols-2">
              {[
                [
                  "My marks look too harsh.",
                  "They are meant to. The board is calibrated against real reported ranges, and most first attempts land below 150. Compare yourself with your own last attempt, not with a cutoff.",
                ],
                [
                  "The board never joined the room.",
                  "A room is convened for one interview only. If you reloaded or came back later, fill your form again and a fresh board will prepare.",
                ],
                [
                  "It could not hear me.",
                  "Check that the browser has microphone permission and that no other app is holding the device. The bar at the bottom of the room shows whether your mic is live.",
                ],
                [
                  "Can I delete an attempt?",
                  "Yes. Email us the session and it goes, transcript included. We do not keep audio at any point.",
                ],
              ].map(([q, a]) => (
                <div key={q}>
                  <dt className="text-[16px] font-semibold text-ink">{q}</dt>
                  <dd className="mt-2 text-[15px] leading-[1.7] text-ink-soft">{a}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      </main>

      <SiteFooter />
    </>
  );
}
