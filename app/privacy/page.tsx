import type { Metadata } from "next";
import { LegalPage, type LegalSection } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "Privacy Policy — PanelMind AI",
  description:
    "What PanelMind AI collects when you sit a mock interview, how long it is kept, and who processes it.",
};

const SECTIONS: LegalSection[] = [
  {
    heading: "What we collect",
    body: ["Only what the product needs to work. Specifically:"],
    list: [
      "Your mobile number or email address, used to sign you in. We do not store passwords because we do not use any.",
      "Your name, so the board can address you.",
      "The contents of your Detailed Application Form — home state and district, education, optional subject, hobbies, service preference, work experience and attempt number.",
      "A written transcript of the interview, both the board's questions and your answers.",
      "The marks, trait scores and remarks each board member produced.",
    ],
  },
  {
    heading: "What we do not keep",
    body: [
      "Your audio. Speech is transcribed to text as you speak and the audio is discarded; no recording of your voice is written to disk or retained after the session ends.",
      "Payment card details. While the product is free in preview we take no payments at all. If that changes, cards will be handled by a PCI-compliant payment processor and never touch our servers.",
    ],
  },
  {
    heading: "Why we hold it",
    body: [
      "Your DAF exists so the board can question you from it — that is the entire premise of the product. Your transcript and marks exist so you can re-read an attempt and compare it with the next one.",
      "We do not sell your data, we do not share it with recruiters or coaching institutes, and we do not use it to advertise to you.",
    ],
  },
  {
    heading: "Who else processes it",
    body: [
      "Running an interview means sending parts of your session to specialist providers. Each receives only what it needs to do its job:",
    ],
    list: [
      "A real-time audio provider, to carry the conversation between you and the board.",
      "A speech-to-text provider, which converts your spoken answers into the transcript.",
      "A text-to-speech provider, which gives each board member a voice.",
      "Large language model providers, which generate the board's questions and produce the marking.",
      "A cloud hosting provider, where the application and database run.",
    ],
  },
  {
    heading: "How long we keep it",
    body: [
      "Your account and your mocks are kept until you ask us to delete them. Email us and an attempt goes, transcript and marks included — or the whole account if you prefer. We action deletion requests within thirty days and confirm when it is done.",
    ],
  },
  {
    heading: "Your rights",
    body: [
      "You can ask us for a copy of everything we hold about you, ask us to correct anything wrong, or ask us to erase it. One email is enough; we will not make you fill in a form or explain why.",
    ],
  },
  {
    heading: "Security",
    body: [
      "Data is encrypted in transit and at rest. Access to production data is limited to the people who need it to operate the service. No system is perfect, and we will tell you promptly if something goes wrong that affects you.",
    ],
  },
  {
    heading: "Changes",
    body: [
      "If this policy changes materially we will say so on this page and update the date above. Continuing to use the product after a change means you accept the revised policy.",
    ],
  },
  {
    heading: "Contact",
    body: [
      "Questions, requests or complaints about privacy go to hello@panelmind.ai and a person will answer.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <LegalPage
      current="/privacy"
      title="Privacy Policy"
      updated="1 August 2026"
      intro="You are handing this product your application form and half an hour of unguarded speech. This page states plainly what happens to that, in the order you would want to be told."
      sections={SECTIONS}
    />
  );
}
