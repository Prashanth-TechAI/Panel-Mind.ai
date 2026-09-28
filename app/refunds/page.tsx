import type { Metadata } from "next";
import { LegalPage, type LegalSection } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "Refunds & Cancellations — PanelMind AI",
  description:
    "PanelMind AI is free while in preview. What happens when paid plans begin, and how refunds work.",
};

const SECTIONS: LegalSection[] = [
  {
    heading: "While the product is free",
    body: [
      "PanelMind AI is currently in preview and costs nothing. There is no card on file, no subscription, and nothing to cancel. You can stop using it at any time and ask us to delete your account and every attempt in it.",
    ],
  },
  {
    heading: "When paid plans begin",
    body: [
      "If and when we start charging, the terms below apply. Existing users will be told before any charge is ever made, and no account will be charged without an explicit action by you.",
    ],
  },
  {
    heading: "If a mock fails",
    body: [
      "If a paid interview fails through a fault on our side — the board does not join, the session drops, or marking does not complete — you get that mock back at no cost, or a full refund of it if you would rather not sit it again.",
      "Tell us within seven days and include the session link. We do not ask you to prove anything; the transcript already shows us what happened.",
    ],
  },
  {
    heading: "If you change your mind",
    body: [
      "An unused mock can be refunded in full within seven days of purchase.",
      "A mock you have already sat cannot be refunded, because the cost of running it — speech, language models, marking — has already been incurred. That is the same reason we will not charge you for one that failed.",
    ],
  },
  {
    heading: "Subscriptions",
    body: [
      "Any subscription can be cancelled at any time from your account. Cancelling stops the next renewal; it does not refund the period already running, and you keep access until that period ends.",
    ],
  },
  {
    heading: "How refunds are paid",
    body: [
      "Refunds go back to the original payment method. Once approved, we submit them within three working days; how quickly the money appears after that is up to your bank or card issuer, typically five to ten working days.",
    ],
  },
  {
    heading: "How to ask",
    body: [
      "Email hello@panelmind.ai with the session or invoice reference. A person reads it. We will tell you the outcome within three working days, and if we say no we will tell you why.",
    ],
  },
];

export default function RefundsPage() {
  return (
    <LegalPage
      current="/refunds"
      title="Refunds & Cancellations"
      updated="1 August 2026"
      intro="Nothing is charged while the product is in preview, so there is nothing to refund today. This page sets out how refunds will work when paid plans begin, so the rules are visible before you ever pay."
      sections={SECTIONS}
    />
  );
}
