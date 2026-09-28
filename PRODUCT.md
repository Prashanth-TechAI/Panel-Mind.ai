# PanelMind AI

**A five-member AI interview board for the UPSC Civil Services Personality Test.**

An aspirant fills their DAF. Five interviewers — a Chairman and four experts —
read it, prepare their own questioning, and interview them aloud for half an
hour. Each member then marks them independently against the seven traits UPSC
publishes, and the candidate is shown the exact moments that cost them marks.

---

## 1. The problem

The Civil Services Personality Test is worth **275 marks** and lasts roughly
half an hour. Candidates reach it having cleared Prelims and Mains — so nobody
fails it on knowledge. Marks are lost on:

- **Judgement** — taking a one-sided position on a contentious issue
- **Structure** — rambling instead of point → reason → example
- **Integrity under pressure** — bluffing instead of admitting ignorance

None of these can be practised from notes. They require a panel that pushes
back. Coaching mocks cost ₹2,000–5,000 a sitting, need scheduling, and — being
run by people trying to be helpful — are usually **kinder than the real board**.
A mock that is easier than the real thing produces false confidence, which for a
fourth-attempt candidate is worse than no mock at all.

### Why an AI board, specifically

| | Coaching mock | PanelMind AI |
|---|---|---|
| Cost | ₹2,000–5,000 | Free in preview |
| Scheduling | Days of lead time | Immediate |
| Repeatability | Once or twice | Unlimited |
| Consistency | Varies by panel | Identical rubric every time |
| Bluff detection | Human panels often let it pass | Challenged and recorded every time |
| Feedback | Verbal, unrecorded | Transcript, per-member scorecard, replayable |

---

## 2. What makes it different

Every other AI interview product is **one interviewer**. This is a **board**.
That distinction is the entire product.

### 2.1 Five members, five portfolios

The DAF is split so no two members can ask the same question:

| | Member | Real counterpart | Owns |
|---|---|---|---|
| **M0** | Chairman | Presiding UPSC Member | identity, family background, service preference, work experience — **and roams freely across any topic** |
| **M1** | Prof. Iyer | Subject expert | education, optional subject |
| **M2** | Shri Rathore | Retired IAS | home state and district, positions of responsibility |
| **M3** | Dr. Menon | Policy and economics | current affairs |
| **M4** | Dr. Kaur | Psychologist | hobbies, sports, languages |

Each has its own voice, its own temperament, its own persona prompt, and its own
private scorecard.

### 2.2 The board never praises

The single most important behavioural rule. Language models are trained to be
encouraging; real boards are not. An AI interviewer that says *"great answer!"*
destroys the illusion instantly and every aspirant notices. Ours gives a flat
*"Hmm."* and moves on.

### 2.3 The bluff detector

The differentiating feature, and the thing real boards actually test.

```
Candidate asserts something → a member challenges it → what do they do?

  DOUBLES DOWN (and was wrong)   → integrity risk, heavy penalty
  CORRECTS THEMSELVES            → integrity credit, what UPSC rewards
  COLLAPSES ENTIRELY             → weak conviction
  SAYS "I DON'T KNOW, SIR"       → strong positive
```

Most aspirants have this backwards: they guess to fill silence. Admitting
ignorance is scored **positively**; guessing is scored **negatively**.

### 2.4 Five independent scorecards

Five evaluators read the same transcript through five different lenses, each
weighted toward its member's priorities, and **none ever sees another's
verdict**. Where they disagree, that spread is itself information — a
consolidated mark from five separate readings is worth more than one model's
opinion rendered five times.

---

## 3. The candidate's journey

```
  1. Sign in (optional)     phone or email → six-digit code → no password
  2. Fill the DAF           ~3 minutes, mirrors the real form
  3. See the split          which member owns which part of your form
  4. Convene the board      ~25s — five members build their question trees
  5. Sit the interview      ~28 min, spoken aloud, microphone live
  6. Read your marks        consolidated /275, five scorecards, what to fix
```

Sign-in is **optional** — anyone may sit a mock. Signing in files the attempt
against an account so it appears under *My mocks* and feeds *My progress*.

---

## 4. Architecture

The system splits into **two planes with opposite requirements**. This is the
central design decision.

```
╔══════════════ HOT PLANE — talking (<800ms, must never stall) ═══════════════╗
║  One brain, one mic. Groq. Speed is everything.                             ║
╚═════════════════════════════════════════════════════════════════════════════╝
                                    │ transcript bus
                                    ▼
╔══════════════ COLD PLANE — judging (async, 5–60s, nobody waits) ════════════╗
║  Five independent evaluators. Claude Sonnet. Quality only.                  ║
╚═════════════════════════════════════════════════════════════════════════════╝
```

Conversation must be fast and never overlap. Judging must be independent and can
be slow. Build them separately and both become easy; fuse them and both become
hard.

### 4.1 The Conductor — the mic token

```
                  ┌──────────────────────────────┐
                  │        CONDUCTOR             │
                  │  pure reducer, no I/O        │
                  │      holds MIC_TOKEN         │
                  └──────────────┬───────────────┘
        ┌────────┬───────────────┼───────────────┬────────┐
      [M0]     [M1]            [M2]            [M3]     [M4]
```

**Exactly one member holds the token at any instant.** Members cannot take the
mic, only release it. Talk-over is *structurally impossible*, not merely
unlikely. `assert_invariants()` runs after every transition; if it ever trips,
the process fails loudly rather than shipping overlapping speech.

States: `idle → chairman_opening → member_block ⟳ → chairman_closing → ended`

Handover is **spoken aloud**, never a silent cut:

> **M2:** "That is all from my side."
> **Chairman:** "Thank you. Dr. Menon, would you like to come in?"

A rolling **digest** travels with the mic so the incoming member can say *"You
mentioned earlier that…"* — this is what makes five agents feel like one board.

### 4.2 Question trees — the latency trick

The single most important performance decision. Before the interview, each
member generates a tree offline:

```
seed ──┬── follow-up 1 ──┬── follow-up 2 ── follow-up 3 ── follow-up 4
       │                 (each assumes the previous was answered well)
```

During a live turn the member does **not invent** a question — it walks the tree
and only rephrases the node in its own voice. That turns a two-second generation
into a two-hundred-millisecond one.

Tuned against a recorded real board: **4 seeds × 5 follow-ups per member, 16
questions per block, most under 15 words**, at least half of them rapid-fire
factual chains:

> *"Which division does Prayagraj fall under?"* → *"How many districts share a
> border?"* → *"Kaushambi was carved out of which district?"*

### 4.3 Latency budget

| Stage | Budget | Measured |
|---|---|---|
| Deepgram final + endpoint | 150–250ms | — |
| Semantic turn detection | ~30ms | — |
| Groq first token | 150–300ms | **303ms** |
| ElevenLabs Flash first chunk | 75–250ms | **310ms warm** |
| LiveKit network | 50–100ms | — |
| **Total** | **≤ 800ms** | |

Techniques: pre-built trees, streaming TTS on the first sentence, persistent
pre-warmed sockets, and **thinking sounds** — the member says *"Hmm."* the
instant the candidate stops, hiding ~500ms invisibly.

### 4.4 Model tiers

| Tier | Model | Provider | Why |
|---|---|---|---|
| **hot** | `llama-3.3-70b-versatile` | Groq | 303ms. Reasoning models were tried and rejected — `gpt-oss-120b` took 882ms and `gpt-oss-20b` failed 1 in 3 with truncated JSON. **Reasoning belongs on the cold tier.** |
| **digest** | `llama-3.1-8b-instant` | Groq | Rolling handover summaries |
| **cold** | `anthropic/claude-sonnet-4.6` | OpenRouter | Question trees and the five evaluators |

### 4.5 Stack

```
backend/          FastAPI · uvicorn · async throughout · uv.lock
  app/domain/     board, DAF, conductor, questions, evaluation  (pure logic)
  app/providers/  llm, tts (with failover), health
  app/            auth, sessions, main
  agent/          LiveKit voice worker
web (root)        Next.js 16 · React 19 · Tailwind v4
```

| Concern | Choice |
|---|---|
| Transport | LiveKit Cloud (India South) |
| STT | Deepgram `nova-3`, `en-IN`, streaming |
| Turn detection | LiveKit semantic end-of-turn model |
| TTS | ElevenLabs `eleven_flash_v2_5`, Deepgram Aura fallback |
| Persistence | JSON on disk (`.sessions.json`, `.accounts.json`) |

### 4.6 TTS failover

ElevenLabs primary, Deepgram Aura fallback, with a **circuit breaker**: a dead
provider still costs ~600ms to reject a request, and paying that on every
utterance would wreck the interview. After a provider-level failure the breaker
trips and subsequent calls skip straight to the fallback.

Cooldowns: quota 5 min · auth 10 min · transient 15s after 3 consecutive.

### 4.7 Evaluation

Five evaluators + a non-LLM **signal extractor** (answer count, words per answer,
filler ratio, admitted-ignorance count, interruptions taken — measured, not
judged). A consolidation agent then writes the feedback.

The seven official UPSC traits are the rubric — not an invented one:

```
mental alertness · critical assimilation · clear exposition · balance of
judgement · depth of interest · social cohesion and leadership · moral integrity
```

**Calibration honesty:** every scorecard carries a note that the mark is
produced by an AI panel, is not calibrated against actual UPSC marks, and should
be used to compare attempts over time — never to predict a result.

---

## 5. Design

Reference standard: **Unacademy, Airbnb, Apple Store**. Light, spacious, bold
sans headings, card grids, one confident accent.

- **Palette** — cream page `#f6f3ec`, navy ink `#1b2a41`, navy accent `#16345e`,
  brass `#b08d2f`. Headings in Playfair Display, body in Archivo.
- **Member colours are validated, not eyeballed.** An earlier hand-picked set
  collapsed M2 against M3 for deuteranopes (ΔE 2.9) — a red-green colourblind
  aspirant could not tell two members apart. Re-run
  `dataviz/scripts/validate_palette.js` before changing them.
- **Charts are bars, never radar.** Radar encodes by area and distorts exactly
  the comparison a candidate needs.
- **No vendor names in the UI.** An aspirant sees a board, not a stack.
- **No emoji.** Line icons only.

---

## 6. Status

### Working and verified

```
✔ Phone or email sign-in, OTP, no password        (optional — not a gate)
✔ DAF intake and portfolio split
✔ Question-tree generation, all five members       ~25s, 72+ questions
✔ LiveKit room, worker dispatch, Chairman opens    verified in Playwright
✔ Mic rotation M0 → M1 → … → close                 verified with real speech
✔ Rambling interrupted, walk-out ends the session
✔ Five evaluators, consolidated /275, bluff detection
✔ TTS failover with circuit breaker
✔ Sessions and accounts survive restarts
```

**Tests:** 143 backend (pytest) · 15 Playwright · plus `@live` suites that
convene a real board and drive a real interview with synthesised speech fed to
Chromium's fake microphone.

### Known gaps

| | Gap | Why it matters |
|---|---|---|
| 1 | **No spoken debrief** | A quarter of a real mock is the Chairman saying what to fix, aloud. We generate the content but only render it as a written scorecard. **Largest fidelity gap.** |
| 2 | **Narrator voices** | Four of five current voices are audiobook/narrator voices — trained to *read*, which is why they sound recited. Professional Indian conversational replacements identified and verified (0.31s warm) but not yet wired in. |
| 3 | **Worker dispatch is implicit** | LiveKit dispatches once at room creation. If no worker is listening, the room is silently dead and the candidate waits 25s to find out. Needs **explicit dispatch** so it fails loudly at "Convene the board". |
| 4 | **Sign-in form redirect** | The API auth flow is sound; driving the three-step form can leave the user on the profile step. |
| 5 | **Dev-mode OTP** | Code is shown on screen and logged. Needs a real SMS/email gateway — one class behind an existing interface. |
| 6 | **JSON persistence** | Fine for one replica. Needs Postgres before real scale. |
| 7 | **No social proof** | Deliberately empty. No fake testimonials or invented user counts will be added. |
| 8 | **No body-language feedback** | Real boards comment on posture and nerves. We have no video. |

---

## 7. Economics

Per 30-minute interview, roughly:

| | |
|---|---|
| STT | ~$0.10 |
| Hot LLM (Groq) | ~$0.10 |
| TTS | ~$0.35 |
| Question trees + 5 evaluators (cold) | ~$0.50 |
| **Total** | **~$1.05** |

Avatars were **deliberately excluded**: live avatar rendering runs $0.10–0.37
per active minute, which would be ~80% of total cost. Voice carries the
experience; five distinct, interrupting, unimpressed voices already feel real.
The interview room uses a single photograph of a seated board with the speaking
member spotlit — the same effect at zero marginal cost.

---

## 8. Running it

```bash
# control plane
cd backend && uv sync --extra dev
uv run uvicorn app.main:app --port 8000

# voice worker (must be running before anyone convenes)
cd backend && BOARD_API_URL=http://127.0.0.1:8000 uv run python -m agent.worker dev

# web
npm install && npm run dev
```

```bash
cd backend && uv run pytest              # 143 offline
cd backend && uv run pytest -m live      # calls real providers
npx playwright test                      # 15 e2e
npx playwright test --grep "@live"       # full interview, real speech
```

**A room is convened for exactly one interview.** Rejoining an old room will
never work — always start from `/daf`.

---

## 9. Roadmap

**Next**
1. Spoken debrief — the Chairman delivers the feedback aloud
2. Swap in professional Indian voices + pre-warm at session start
3. Explicit agent dispatch

**Then**
4. Postgres for sessions and accounts
5. Real SMS/email OTP gateway
6. Hindi interviews — Deepgram and ElevenLabs both support it, and real UPSC
   interviews are conducted in Hindi. Almost nobody offers this.
7. Personalised practice plan driven by the evaluators' own flags
8. Recorded playback

**Later**
9. Live avatars, once revenue justifies the cost
10. Score calibration against users' actual reported UPSC marks

---

## 10. Principles

1. **Aspirant trust above all.** A mock easier than the real board produces
   false confidence. For a fourth-attempt candidate that is worse than nothing.
2. **Never present an AI mark as a UPSC mark.** The disclaimer travels with the
   score, always.
3. **Never fabricate social proof.** No invented testimonials, no made-up user
   counts — not for a product people spend ₹40,000 on coaching for.
4. **The board never praises.** Break this and the whole illusion goes.
5. **Show the aspirant a board, not a stack.** No vendor names, no agent counts,
   no model names in the UI.
6. **Fail loudly.** A silently dead room is worse than an error message.
