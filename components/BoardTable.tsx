"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { voiceUrl, type BoardMember } from "@/lib/api";

/**
 * The board, seated.
 *
 * A real UPSC board sits in a shallow arc with the Chairman at the centre.
 * The layout mirrors that rather than using a flat grid, and each nameplate
 * plays that member's actual voice so the five personalities are audible
 * before the interview ever starts.
 */

/** A line each member would plausibly open with, from their own portfolio. */
const OPENING_LINES: Record<string, string> = {
  M0: "Please, come in. Have a seat. So — tell us what brought you here.",
  M1: "You listed Sociology as your optional. Explain Durkheim's idea of anomie.",
  M2: "Hmm. You are from Jhansi. What is the biggest administrative failure there?",
  M3: "Yes, but that is only one side of it. What about the fiscal cost?",
  M4: "You mention reading. Which was the last book, and what did you disagree with?",
};

/** Vertical offset in the arc, Chairman highest. Desktop only. */
const ARC_OFFSET: Record<string, string> = {
  M1: "lg:translate-y-10",
  M2: "lg:translate-y-3",
  M0: "lg:-translate-y-4",
  M3: "lg:translate-y-3",
  M4: "lg:translate-y-10",
};

/** Seating order: Chairman centre, members flanking. */
const SEATING = ["M1", "M2", "M0", "M3", "M4"] as const;

type PlayState = "idle" | "loading" | "speaking" | "failed";

export function BoardTable({ members }: { members: BoardMember[] }) {
  const [active, setActive] = useState<string | null>(null);
  const [state, setState] = useState<PlayState>("idle");
  const [provider, setProvider] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const seated = SEATING.map((id) => members.find((m) => m.id === id)).filter(
    (m): m is BoardMember => m !== undefined,
  );

  const stop = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    setActive(null);
    setState("idle");
  }, []);

  useEffect(() => stop, [stop]);

  const speak = useCallback(
    async (member: BoardMember) => {
      if (active === member.id) {
        stop();
        return;
      }

      audioRef.current?.pause();
      setActive(member.id);
      setState("loading");
      setProvider(null);

      try {
        // Fetch rather than setting audio.src directly so the response headers
        // are readable — they say which provider actually spoke.
        const res = await fetch(voiceUrl(member.id, OPENING_LINES[member.id]));
        if (!res.ok) throw new Error(`voice unavailable (${res.status})`);

        setProvider(res.headers.get("X-Tts-Provider"));

        const url = URL.createObjectURL(await res.blob());
        const audio = new Audio(url);
        audioRef.current = audio;

        audio.addEventListener("ended", () => {
          URL.revokeObjectURL(url);
          setActive(null);
          setState("idle");
        });

        await audio.play();
        setState("speaking");
      } catch {
        setState("failed");
        setTimeout(() => setState("idle"), 2400);
      }
    },
    [active, stop],
  );

  return (
    <div>
      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5 lg:gap-3">
        {seated.map((member, index) => {
          const isActive = active === member.id;

          return (
            <li
              key={member.id}
              className={`animate-rise ${ARC_OFFSET[member.id] ?? ""}`}
              style={{ animationDelay: `${index * 90 + 200}ms` }}
            >
              <button
                type="button"
                onClick={() => speak(member)}
                aria-pressed={isActive}
                aria-label={`Hear ${member.name}, ${member.title}`}
                data-testid={`member-${member.id}`}
                data-state={isActive ? state : "idle"}
                className="group relative flex w-full cursor-pointer flex-col items-center rounded-sm bg-surface px-4 pt-7 pb-5 text-center transition-all duration-500 hover:bg-surface-sunk focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brass"
                style={{
                  boxShadow: isActive
                    ? `0 0 0 1px ${member.accent}66, 0 -18px 44px -18px ${member.accent}`
                    : "0 0 0 1px #1a151218",
                }}
              >
                {/* The lamp above whoever is speaking. */}
                <span
                  aria-hidden
                  className={`pointer-events-none absolute inset-x-0 top-0 h-24 rounded-t-sm transition-opacity duration-500 ${
                    isActive ? "animate-lamp opacity-100" : "opacity-0"
                  }`}
                  style={{
                    background: `radial-gradient(70% 100% at 50% 0%, ${member.accent}40, transparent 72%)`,
                  }}
                />

                {/* Brass nameplate. */}
                <span className="brass-plate relative mb-4 block w-full rounded-[2px] px-2 py-2">
                  <span className="engraved block font-display text-[15px] leading-tight font-semibold tracking-tight">
                    {member.name}
                  </span>
                  <span className="engraved mt-0.5 block font-mono text-[9px] tracking-official uppercase opacity-80">
                    {member.title}
                  </span>
                </span>

                <span className="mb-3 block min-h-[3.5rem] text-[13px] leading-snug text-ink/65">
                  {member.role}
                </span>

                {/* State readout. Doubles as the play affordance. */}
                <span className="flex h-5 items-center justify-center gap-1.5">
                  {isActive && state === "speaking" ? (
                    <>
                      {[0, 1, 2, 3, 4].map((bar) => (
                        <span
                          key={bar}
                          className="animate-waveform block h-4 w-[3px] rounded-full"
                          style={{
                            background: member.accent,
                            animationDelay: `${bar * 110}ms`,
                          }}
                        />
                      ))}
                    </>
                  ) : isActive && state === "loading" ? (
                    <span className="font-mono text-[10px] tracking-official text-ink-soft uppercase">
                      connecting
                    </span>
                  ) : state === "failed" && isActive ? (
                    <span className="font-mono text-[10px] tracking-official text-danger uppercase">
                      no voice
                    </span>
                  ) : (
                    <span className="font-mono text-[10px] tracking-official text-ink-faint uppercase transition-colors group-hover:text-brass">
                      ▸ hear voice
                    </span>
                  )}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <p className="mt-14 text-center font-mono text-[10px] tracking-official text-ink-faint uppercase lg:mt-20">
        {provider
          ? `voice synthesised by ${provider}`
          : "select a member to hear them speak"}
      </p>
    </div>
  );
}
