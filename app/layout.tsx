import type { Metadata } from "next";
import {
  Playfair_Display,
  Source_Serif_4,
  Spline_Sans_Mono,
} from "next/font/google";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
});

// A text serif for body copy — Playfair is a display face and falls apart at
// paragraph sizes. Source Serif is drawn for screen reading and shares
// Playfair's vertical stress, so the two sit together as one voice.
const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
});

const splineMono = Spline_Sans_Mono({
  variable: "--font-spline-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PanelMind AI — UPSC Personality Test Simulator",
  description:
    "Face a five-member UPSC interview board. They question from your DAF, they do not praise you, and each one scores you independently.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${playfair.variable} ${sourceSerif.variable} ${splineMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
