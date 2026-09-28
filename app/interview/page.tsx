"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Room,
  RoomEvent,
  Track,
  type RemoteTrack,
  type RemoteTrackPublication,
} from "livekit-client";
import { getBoard, type BoardMember } from "@/lib/api";
import { BoardPreparing } from "@/components/BoardPreparing";
import { clearDafDraft, dafPayload, readDafDraft } from "@/lib/daf";
import {
  PHASE_LABEL,
  STATE_TOPIC,
  TRANSCRIPT_TOPIC,
  clearSession,
  formatClock,
  createSession,
  takeSession,
  type BoardState,
  type SessionCredentials,
  type Utterance,
} from "@/lib/interview";

/**
 * The interview room.
 *
 * The five seats are the interface. Whoever holds the mic is lit; the rest sit
 * back, listening. Nothing here tells the candidate how they are doing — that
 * would break the whole premise.
 */

type Connection = "idle" | "connecting" | "live" | "ended" | "failed";

/**
 * Seat positions, measured from the board-room photograph as a percentage of
 * its width. The order matches a real panel: Chairman at the centre.
 */
const SEATS: { id: string; x: number }[] = [
  { id: "M1", x: 12.7 },
  { id: "M2", x: 29.9 },
  { id: "M0", x: 50.9 },
  { id: "M3", x: 70.6 },
  { id: "M4", x: 88.3 },
];

/** The room photograph's aspect, used to size the stage so it always covers. */
const ROOM_AR = 1719 / 915;

/** The Chairman opens within seconds. Past this, something is wrong. */
const BOARD_SILENT_AFTER_MS = 25_000;

export default function InterviewPage() {
  const router = useRouter();
  const [connection, setConnection] = useState<Connection>("idle");
  const [error, setError] = useState<string | null>(null);
  const [members, setMembers] = useState<BoardMember[]>([]);
  const [state, setState] = useState<BoardState | null>(null);
  const [transcript, setTranscript] = useState<Utterance[]>([]);
  const [muted, setMuted] = useState(false);
  const [clock, setClock] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [boardSilent, setBoardSilent] = useState(false);
  const [creds, setCreds] = useState<SessionCredentials | null>(null);
  const [preparing, setPreparing] = useState(true);
  // The record stays shut unless asked for. Reading along turns an interview
  // into a transcript-checking exercise, which is not what is being trained.
  const [showTranscript, setShowTranscript] = useState(false);
  // Set when a board voice track actually arrives — the earliest hard proof
  // that a member is really there, rather than that we merely joined a room.
  const [boardAudible, setBoardAudible] = useState(false);

  const roomRef = useRef<Room | null>(null);
  const audioRef = useRef<HTMLDivElement | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    getBoard()
      .then((board) => setMembers(board.members))
      .catch(() => setError("We could not load the board."));
  }, []);

  useEffect(() => {
    if (connection !== "live") return;
    const timer = setInterval(() => setClock((ms) => ms + 1000), 1000);
    return () => clearInterval(timer);
  }, [connection]);

  useEffect(() => {
    transcriptRef.current?.scrollTo({
      top: transcriptRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [transcript]);

  /**
   * Being in the room is not the same as the board being in it. Showing five
   * seated members while nothing is happening reads as a broken product — and
   * worse, as a claim that they are there when they may not be. So the panel
   * stays hidden until there is real evidence a member has begun: a voice
   * track, a first line of transcript, or the board leaving its idle phase.
   */
  const boardArrived =
    boardAudible || transcript.length > 0 || (state !== null && state.phase !== "idle");

  /**
   * The board opens within seconds of the candidate sitting down. If no state
   * ever arrives, no member took the job — say so plainly rather than leaving
   * them staring at an empty room.
   */
  useEffect(() => {
    if (connection !== "live" || boardArrived) return;
    const timer = setTimeout(() => setBoardSilent(true), BOARD_SILENT_AFTER_MS);
    return () => clearTimeout(timer);
  }, [connection, boardArrived]);


  /**
   * Convene on arrival. A session already stashed (an older entry point) is
   * used as-is; otherwise the DAF draft is turned into one here, so the wait
   * has a screen of its own and the join button lands on the same page as the
   * microphone prompt.
   */
  useEffect(() => {
    const existing = takeSession();
    if (existing) {
      setCreds(existing);
      setPreparing(false);
      return;
    }

    const draft = readDafDraft();
    if (!draft) {
      setError("No interview is prepared. Fill your form first.");
      setPreparing(false);
      setConnection("failed");
      return;
    }

    let cancelled = false;
    createSession(dafPayload(draft.form) as never)
      .then((c) => {
        if (cancelled) return;
        setCreds(c);
        clearDafDraft();
        setPreparing(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "The board could not be convened.");
        setPreparing(false);
        setConnection("failed");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const connect = useCallback(async () => {
    const credentials = creds;
    if (!credentials) {
      setError("No interview is prepared. Fill your form first.");
      setConnection("failed");
      return;
    }

    setConnection("connecting");
    setError(null);

    const room = new Room({ adaptiveStream: true, dynacast: true });
    roomRef.current = room;
    const decoder = new TextDecoder();

    room
      .on(RoomEvent.DataReceived, (payload, _p, _k, topic) => {
        try {
          const data = JSON.parse(decoder.decode(payload));
          if (topic === STATE_TOPIC) {
            setState(data as BoardState);
            setClock((data as BoardState).elapsed_ms);
            if ((data as BoardState).phase === "ended") setConnection("ended");
          } else if (topic === TRANSCRIPT_TOPIC) {
            setTranscript((prev) => [...prev, data as Utterance]);
          }
        } catch {
          // A malformed frame must not take the room down.
        }
      })
      .on(RoomEvent.TrackSubscribed, (track: RemoteTrack, _pub: RemoteTrackPublication) => {
        if (track.kind === Track.Kind.Audio && audioRef.current) {
          audioRef.current.appendChild(track.attach());
          setBoardAudible(true);
        }
      })
      .on(RoomEvent.Disconnected, () => {
        setConnection((prev) => (prev === "ended" ? "ended" : "failed"));
      });

    try {
      await room.connect(credentials.livekit_url, credentials.token);
      await room.localParticipant.setMicrophoneEnabled(true);
      setSessionId(credentials.session_id);
      setConnection("live");
    } catch (err) {
      setError(
        err instanceof Error && /permission|denied|NotAllowed/i.test(err.message)
          ? "Microphone access was blocked. The board cannot hear you."
          : "We could not put you in the room. Please try again.",
      );
      setConnection("failed");
    }
  }, [creds]);

  useEffect(() => {
    return () => {
      roomRef.current?.disconnect();
      roomRef.current = null;
    };
  }, []);

  const toggleMute = useCallback(async () => {
    const room = roomRef.current;
    if (!room) return;
    const next = !muted;
    await room.localParticipant.setMicrophoneEnabled(!next);
    setMuted(next);
  }, [muted]);

  const seated = SEATS.map((seat) => ({
    seat,
    member: members.find((m) => m.id === seat.id),
  })).filter((s): s is { seat: (typeof SEATS)[number]; member: BoardMember } =>
    s.member !== undefined,
  );
  const micHolder = state?.mic_holder ?? null;
  const live = connection === "live" || connection === "ended";
  const inRoom = live && boardArrived;


  return (
    <main className="flex min-h-dvh flex-col bg-page">
      {/* --- Room bar. Only before the room; inside it the chrome floats on
              the image instead, so nothing frames the board. --- */}
      {!live && (
        <header className="sticky top-0 z-40 border-b border-line bg-page/85 backdrop-blur-xl">
          <div className="mx-auto flex h-16 w-full max-w-[1300px] items-center justify-between gap-4 px-6 sm:px-8">
            <Link href="/" className="text-[14px] font-medium text-ink-soft hover:text-ink">
              ← Leave
            </Link>
            <div className="flex items-center gap-5">
              <span
                data-testid="phase"
                className="rounded-full bg-surface-sunk px-3 py-1 text-[12px] font-medium text-ink-soft"
              >
                {state ? PHASE_LABEL[state.phase] : "Not convened"}
              </span>
              <span data-testid="clock" className="font-mono text-[15px] tabular-nums text-ink">
                {formatClock(clock)}
              </span>
            </div>
          </div>
        </header>
      )}

      {/* --- Convening: its own screen, not a spinner in a button --- */}
      {!live && preparing && (
        <div className="flex flex-1 items-center justify-center px-6 py-20">
          <BoardPreparing members={members} done={false} error={error} />
        </div>
      )}

      {/* --- Before joining --- */}
      {!live && !preparing && (
        <div className="flex flex-1 items-center justify-center px-6 py-20">
          <div className="w-full max-w-md text-center">
            <h1 className="text-[30px] leading-tight font-bold tracking-[-0.03em] text-balance">
              {connection === "connecting"
                ? "Taking your seat…"
                : connection === "failed"
                  ? "We could not get you in"
                  : "The board is ready for you"}
            </h1>

            {error ? (
              <p
                data-testid="join-error"
                role="alert"
                className="mt-5 rounded-xl bg-danger-wash px-4 py-3 text-left text-[14px] text-danger"
              >
                {error}
              </p>
            ) : (
              <p className="mt-4 text-[15px] leading-relaxed text-ink-soft">
                Your microphone will be on. Speak as you would in the real room —
                they will interrupt you if you ramble.
              </p>
            )}

            <div className="mt-8 flex flex-col items-center gap-3">
              <button
                type="button"
                onClick={connect}
                disabled={connection === "connecting"}
                data-testid="join"
                className="w-full rounded-full bg-accent px-8 py-3.5 text-[15px] font-semibold text-white transition-colors hover:bg-accent-deep disabled:opacity-50"
              >
                {connection === "connecting" ? "Entering…" : "May I come in, sir?"}
              </button>
              {connection === "failed" && (
                <Link href="/daf" className="text-[14px] font-medium text-accent hover:underline">
                  Fill your form
                </Link>
              )}
            </div>
          </div>
        </div>
      )}

      {/* --- Seated, waiting to be called. The board is not shown until it
              is genuinely there. --- */}
      {live && !boardArrived && !boardSilent && (
        <div className="fixed inset-0 z-40 flex flex-col items-center justify-center bg-[#0d0b08] px-6 text-center">
          <span className="relative grid size-16 place-items-center">
            <span className="absolute inset-0 animate-ping rounded-full bg-brass/25" />
            <span className="relative size-3 rounded-full bg-brass" />
          </span>
          <h1 className="mt-9 font-display text-[clamp(1.6rem,3vw,2.2rem)] font-bold text-balance text-white">
            You are seated.
          </h1>
          <p className="mt-3 max-w-sm text-[15px] leading-relaxed text-white/55">
            Wait for the Chairman to open. Your microphone is already live — do
            not speak until you are addressed.
          </p>
          <button
            type="button"
            onClick={async () => {
              await roomRef.current?.disconnect();
              router.push("/");
            }}
            className="mt-10 text-[14px] font-medium text-white/40 transition-colors hover:text-white/80"
          >
            Walk out
          </button>
        </div>
      )}

      {/* --- The board never came. Its own screen, not a note in a drawer. --- */}
      {live && !boardArrived && boardSilent && (
        <div
          data-testid="board-silent"
          role="alert"
          className="fixed inset-0 z-40 flex flex-col items-center justify-center bg-[#0d0b08] px-6 text-center"
        >
          <h1 className="font-display text-[clamp(1.6rem,3vw,2.2rem)] font-bold text-balance text-white">
            The board did not take their seats.
          </h1>
          <p className="mt-4 max-w-md text-[15px] leading-relaxed text-white/55">
            You are in the room, but no member joined. A room is convened for
            one sitting — if this interview has already been sat, it cannot be
            reopened.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/daf"
              className="rounded-full bg-white px-6 py-3 text-[15px] font-semibold text-ink transition-opacity hover:opacity-90"
            >
              Convene a fresh board
            </Link>
            <button
              type="button"
              onClick={async () => {
                await roomRef.current?.disconnect();
                router.push("/");
              }}
              className="rounded-full px-5 py-3 text-[15px] font-medium text-white/55 transition-colors hover:text-white"
            >
              Walk out
            </button>
          </div>
        </div>
      )}

      {/* --- In the room ---

          Full-bleed and chrome-free: no nav, no page background, no card
          around the board. The image and the seat overlays share one box sized
          to *cover* the viewport at the photograph's own aspect ratio, because
          the seat positions are percentages measured against that photograph —
          letting the image crop independently would slide every nameplate off
          its chair. --- */}
      {inRoom && (
        <div className="animate-rise fixed inset-0 z-40 overflow-hidden bg-black">
          <div
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
            style={{
              width: `max(100vw, calc(100dvh * ${ROOM_AR}))`,
              aspectRatio: "1719 / 915",
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/board-room.png"
              alt="The interview board seated at their table"
              className="absolute inset-0 h-full w-full select-none object-cover"
              draggable={false}
            />

            {/* Dim the room, then lift whoever holds the mic out of it. */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 transition-opacity duration-700"
              style={{ background: micHolder ? "#0d0b0899" : "#0d0b0855" }}
            />

            {seated.map(({ seat, member }) => {
              const speaking = micHolder === member.id;
              const done = state?.completed_blocks.includes(member.id);

              return (
                <div
                  key={member.id}
                  data-testid={`seat-${member.id}`}
                  data-speaking={speaking ? "true" : "false"}
                  className="absolute top-0 bottom-0 -translate-x-1/2"
                  style={{ left: `${seat.x}%`, width: "19%" }}
                >
                  {/* Spotlight on the member currently questioning. */}
                  <span
                    aria-hidden
                    className={`pointer-events-none absolute inset-0 transition-opacity duration-700 ${
                      speaking ? "opacity-100" : "opacity-0"
                    }`}
                    style={{
                      background: `radial-gradient(58% 46% at 50% 46%, ${member.accent}3d 0%, transparent 72%)`,
                      mixBlendMode: "screen",
                    }}
                  />

                  {/* Nameplate on the table edge. */}
                  <span
                    className="absolute bottom-[31%] left-1/2 w-[86%] -translate-x-1/2 rounded-lg px-2 py-1.5 text-center backdrop-blur-sm transition-all duration-500"
                    style={{
                      background: speaking ? "#ffffffee" : "#ffffff26",
                      boxShadow: speaking ? `0 0 0 2px ${member.accent}` : "none",
                    }}
                  >
                    <span
                      className="block truncate text-[clamp(9px,0.85vw,13px)] font-semibold"
                      style={{ color: speaking ? "var(--color-ink)" : "#ffffffe6" }}
                    >
                      {member.name}
                    </span>
                    <span
                      className="mt-0.5 flex h-3 items-center justify-center gap-[3px]"
                      style={{ color: speaking ? "var(--color-ink-soft)" : "#ffffff99" }}
                    >
                      {speaking ? (
                        [0, 1, 2, 3].map((bar) => (
                          <span
                            key={bar}
                            className="animate-waveform block h-2.5 w-[2.5px] rounded-full"
                            style={{
                              background: member.accent,
                              animationDelay: `${bar * 120}ms`,
                            }}
                          />
                        ))
                      ) : (
                        <span className="text-[clamp(7px,0.6vw,10px)]">
                          {done ? "Finished" : "Listening"}
                        </span>
                      )}
                    </span>
                  </span>
                </div>
              );
            })}
          </div>

          {/* --- Floating chrome. Sits on the room, never frames it. --- */}
          <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-4 bg-gradient-to-b from-black/55 to-transparent p-5 sm:p-6">
            <button
              type="button"
              onClick={async () => {
                await roomRef.current?.disconnect();
                router.push("/");
              }}
              data-testid="leave"
              className="pointer-events-auto flex items-center gap-2 rounded-full bg-black/35 px-4 py-2.5 text-[14px] font-medium text-white/85 backdrop-blur-md transition-colors hover:bg-black/55 hover:text-white"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M15 5l-7 7 7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Walk out
            </button>

            <div className="pointer-events-auto flex items-center gap-3 rounded-full bg-black/35 px-4 py-2.5 backdrop-blur-md">
              <span data-testid="phase" className="text-[13px] font-medium text-white/75">
                {state ? PHASE_LABEL[state.phase] : "Not convened"}
              </span>
              <span aria-hidden className="h-3 w-px bg-white/25" />
              <span data-testid="clock" className="font-mono text-[15px] tabular-nums text-white">
                {formatClock(clock)}
              </span>
            </div>
          </div>

          {/* --- Controls --- */}
          <div className="absolute inset-x-0 bottom-0 flex flex-wrap items-center justify-center gap-3 bg-gradient-to-t from-black/65 to-transparent p-5 sm:p-7">
            {connection === "ended" ? (
              <>
                <p data-testid="ended" className="text-[15px] font-medium text-white/85">
                  The interview is over.
                </p>
                {sessionId && (
                  <Link
                    href={`/report?session=${sessionId}`}
                    data-testid="see-marks"
                    className="rounded-full bg-white px-6 py-3 text-[15px] font-semibold text-accent transition-opacity hover:opacity-90"
                  >
                    See your marks →
                  </Link>
                )}
              </>
            ) : (
              <button
                type="button"
                onClick={toggleMute}
                data-testid="mute"
                className={`flex items-center gap-2.5 rounded-full px-6 py-3 text-[15px] font-medium backdrop-blur-md transition-colors ${
                  muted
                    ? "bg-danger text-white"
                    : "bg-white/90 text-ink hover:bg-white"
                }`}
              >
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden>
                  <rect x="9" y="3" width="6" height="11" rx="3" stroke="currentColor" strokeWidth="1.7" />
                  <path d="M5 11a7 7 0 0 0 14 0M12 18v3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
                  {muted && <path d="M4 4l16 16" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />}
                </svg>
                {muted ? "Microphone off" : "Microphone on"}
              </button>
            )}

            <button
              type="button"
              onClick={() => setShowTranscript((v) => !v)}
              aria-expanded={showTranscript}
              aria-controls="transcript-panel"
              data-testid="transcript-toggle"
              className="flex items-center gap-2.5 rounded-full bg-black/40 px-5 py-3 text-[15px] font-medium text-white/85 backdrop-blur-md transition-colors hover:bg-black/60 hover:text-white"
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden>
                <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="1.7" />
                <path d="M7 10h10M7 14h6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
              </svg>
              Transcript
              {transcript.length > 0 && (
                <span className="rounded-full bg-white/20 px-2 py-0.5 font-mono text-[12px] tabular-nums">
                  {transcript.length}
                </span>
              )}
            </button>
          </div>

          {/* --- The record, on request --- */}
          {showTranscript && (
            <aside
              id="transcript-panel"
              data-testid="transcript"
              className="animate-rise absolute inset-y-0 right-0 flex w-full max-w-[440px] flex-col border-l border-white/10 bg-page/95 backdrop-blur-xl"
            >
              <div className="flex items-center justify-between border-b border-line px-5 py-4">
                <h2 className="text-[16px] font-semibold">Record of proceedings</h2>
                <button
                  type="button"
                  onClick={() => setShowTranscript(false)}
                  aria-label="Close transcript"
                  className="grid size-8 place-items-center rounded-full text-ink-soft transition-colors hover:bg-surface-sunk hover:text-ink"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
                    <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                  </svg>
                </button>
              </div>

              <div ref={transcriptRef} className="flex-1 space-y-5 overflow-y-auto p-5">
                {transcript.length === 0 ? (
                  <p className="text-[14px] text-ink-faint">
                    Nothing said yet.
                  </p>
                ) : (
                  transcript.map((line, index) => {
                    const member = members.find((m) => m.id === line.member_id);
                    const isCandidate = line.member_id === null;

                    return (
                      <p key={`${line.turn}-${index}`} className="animate-rise">
                        <span
                          className="text-[12px] font-semibold"
                          style={{ color: member?.accent ?? "var(--color-ink-soft)" }}
                        >
                          {line.speaker}
                        </span>
                        <span
                          className={`mt-1 block text-[15px] leading-relaxed ${
                            isCandidate ? "text-ink" : "text-ink-soft"
                          }`}
                        >
                          {line.text}
                        </span>
                      </p>
                    );
                  })
                )}
              </div>
            </aside>
          )}
        </div>
      )}

      <div ref={audioRef} className="hidden" aria-hidden />
    </main>
  );
}
