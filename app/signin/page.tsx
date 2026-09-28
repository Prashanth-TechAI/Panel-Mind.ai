"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { apiPost, getToken, useAuth, type Account } from "@/lib/auth";

/**
 * Sign in.
 *
 * Three steps, one field each. A returning aspirant only ever sees two of
 * them; name and email are asked once, on the first sign-in, and never again.
 */

type Step = "phone" | "code" | "profile";

const CODE_LENGTH = 6;

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-[13px] font-medium text-ink">{label}</span>
      {children}
      {hint && <span className="mt-2 block text-[12px] text-ink-soft">{hint}</span>}
    </label>
  );
}

const inputClass =
  "mt-2 w-full rounded-xl border border-line bg-surface px-4 py-3.5 text-[15px] text-ink outline-none transition-all placeholder:text-ink-faint focus:border-accent focus:ring-4 focus:ring-accent/10";

function SignInBody() {
  const router = useRouter();
  const params = useSearchParams();
  // Signing in from the header should return you home, not drop you
  // into the application form. Only a gated page passes ?next=.
  const next = params.get("next") ?? "/";
  const { account, adopt } = useAuth();

  const [step, setStep] = useState<Step>("phone");
  const [identifier, setIdentifier] = useState("");
  const [missing, setMissing] = useState<string[]>([]);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [returning, setReturning] = useState(false);
  const codeRef = useRef<HTMLInputElement | null>(null);
  // The last code we tried, so a wrong one is not retried forever.
  const attempted = useRef<string | null>(null);

  useEffect(() => {
    if (account?.is_complete) router.replace(next);
  }, [account, next, router]);

  useEffect(() => {
    if (step === "code") codeRef.current?.focus();
  }, [step]);

  /**
   * Submit the moment six digits are present — typed, pasted, autofilled from
   * an SMS, or prefilled in development. Waiting for a button press after the
   * last digit is friction nobody wants.
   *
   * `attempted` guards against resubmitting the same code: a wrong one must be
   * corrected by the candidate, not retried in a loop.
   */
  useEffect(() => {
    if (step !== "code" || busy) return;
    if (code.length !== CODE_LENGTH) return;
    if (attempted.current === code) return;

    attempted.current = code;
    void verify();
    // `verify` is stable for the fields it reads; re-running on its identity
    // would resubmit on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, step, busy]);

  async function sendCode(event?: React.FormEvent) {
    event?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await apiPost<{
        returning_user: boolean;
        dev_code?: string;
      }>("/api/auth/start", { identifier });
      setReturning(res.returning_user);
      setDevCode(res.dev_code ?? null);
      // In development the code comes back with the send. Fill it in — the
      // effect below then submits it, so there is nothing to type.
      setCode(res.dev_code ?? "");
      setStep("code");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the code.");
    } finally {
      setBusy(false);
    }
  }

  async function verify(event?: React.FormEvent) {
    event?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await apiPost<{
        token: string;
        user: Account;
        needs_profile: boolean;
        missing: string[];
      }>("/api/auth/verify", { identifier, code });

      setMissing(res.missing ?? []);
      adopt(res.token, res.user);
      if (res.needs_profile) setStep("profile");
      else router.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not verify the code.");
      setCode("");
      codeRef.current?.focus();
    } finally {
      setBusy(false);
    }
  }

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await apiPost<{ user: Account }>("/api/auth/profile", {
        name,
        ...(missing.includes("email") ? { email } : {}),
        ...(missing.includes("phone") ? { phone } : {}),
      });
      adopt(getToken()!, res.user);
      // A full navigation rather than a client transition: the destination
      // guards on auth state, and a soft replace can outrun it.
      window.location.assign(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your details.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-dvh flex-col">
      <header className="px-6 py-6 sm:px-10">
        <Link href="/" className="inline-flex items-center gap-2.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo-mark.svg"
            alt=""
            width={58}
            height={48}
            className="h-12 w-auto shrink-0"
          />
          <span className="font-display text-[23px] leading-none font-bold tracking-[-0.015em] text-ink">
            PanelMind <span className="text-accent-bright">AI</span>
          </span>
        </Link>
      </header>

      <div className="flex flex-1 items-start justify-center px-6 pt-8 pb-20 sm:pt-16">
        <div className="w-full max-w-[420px]">
          {/* --- Step: phone --- */}
          {step === "phone" && (
            <form onSubmit={sendCode} className="animate-rise" data-testid="step-phone">
              <h1 className="text-[30px] leading-[1.15] font-semibold tracking-[-0.02em] text-ink">
                Sign in or create
                <br />
                your account
              </h1>
              <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">
                Enter your mobile number or email and we&rsquo;ll send a
                six-digit code. No password to remember.
              </p>

              <div className="mt-8">
                <Field
                  label="Mobile number or email"
                  hint="Indian numbers work without the +91."
                >
                  <input
                    autoFocus
                    required
                    autoComplete="username"
                    name="identifier"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder="98765 43210  or  you@example.com"
                    className={inputClass}
                    data-testid="phone-input"
                  />
                </Field>
              </div>

              {error && <ErrorNote>{error}</ErrorNote>}

              <button
                type="submit"
                disabled={busy || identifier.trim().length < 5}
                data-testid="send-code"
                className="mt-6 w-full rounded-xl bg-accent px-6 py-3.5 text-[15px] font-medium text-white transition-all hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? "Sending…" : "Continue"}
              </button>

              <p className="mt-6 text-[12px] leading-relaxed text-ink-faint">
                By continuing you agree that mock scores are indicative and not
                affiliated with the Union Public Service Commission.
              </p>
            </form>
          )}

          {/* --- Step: code --- */}
          {step === "code" && (
            <form onSubmit={verify} className="animate-rise" data-testid="step-code">
              <h1 className="text-[30px] leading-[1.15] font-semibold tracking-[-0.02em] text-ink">
                Enter the code
              </h1>
              <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">
                Sent to <span className="font-medium text-ink">{identifier}</span>.{" "}
                <button
                  type="button"
                  onClick={() => {
                    setStep("phone");
                    setError(null);
                  }}
                  className="font-medium text-accent underline underline-offset-2"
                >
                  Change
                </button>
              </p>

              <div className="mt-8">
                <Field label="Six-digit code">
                  <input
                    ref={codeRef}
                    required
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={CODE_LENGTH}
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                    placeholder="······"
                    className={`${inputClass} text-center font-mono text-[24px] tracking-[0.4em]`}
                    data-testid="code-input"
                  />
                </Field>
              </div>

              {devCode && (
                <p
                  data-testid="dev-code"
                  className="mt-4 rounded-xl bg-accent-wash px-4 py-3 text-[13px] text-accent-deep"
                >
                  Development mode — code{" "}
                  <span className="font-mono font-semibold">{devCode}</span>{" "}
                  filled in and submitted for you
                </p>
              )}

              {error && <ErrorNote>{error}</ErrorNote>}

              <button
                type="submit"
                disabled={busy || code.length !== CODE_LENGTH}
                data-testid="verify-code"
                className="mt-6 w-full rounded-xl bg-accent px-6 py-3.5 text-[15px] font-medium text-white transition-all hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy
                  ? "Checking…"
                  : code.length === CODE_LENGTH
                    ? "Signing you in…"
                    : returning
                      ? "Sign in"
                      : "Create account"}
              </button>

              <button
                type="button"
                onClick={() => sendCode()}
                disabled={busy}
                className="mt-4 w-full text-[13px] text-ink-soft transition-colors hover:text-ink"
              >
                Didn&rsquo;t get it? Send again
              </button>
            </form>
          )}

          {/* --- Step: profile --- */}
          {step === "profile" && (
            <form onSubmit={saveProfile} className="animate-rise" data-testid="step-profile">
              <h1 className="text-[30px] leading-[1.15] font-semibold tracking-[-0.02em] text-ink">
                Almost there
              </h1>
              <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">
                The board addresses you by name. We ask this once.
              </p>

              <div className="mt-8 space-y-5">
                <Field label="Full name">
                  <input
                    autoFocus
                    required
                    name="name"
                    autoComplete="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Rohit Sharma"
                    className={inputClass}
                    data-testid="name-input"
                  />
                </Field>

                {missing.includes("email") && (
                  <Field label="Email" hint="Your scorecards are sent here.">
                    <input
                      required
                      type="email"
                      name="email"
                      autoComplete="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="rohit@example.com"
                      className={inputClass}
                      data-testid="email-input"
                    />
                  </Field>
                )}

                {missing.includes("phone") && (
                  <Field
                    label="Mobile number"
                    hint="So you can also sign in with your number."
                  >
                    <input
                      required
                      inputMode="tel"
                      name="phone"
                      autoComplete="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="98765 43210"
                      className={inputClass}
                      data-testid="profile-phone-input"
                    />
                  </Field>
                )}
              </div>

              {error && <ErrorNote>{error}</ErrorNote>}

              <button
                type="submit"
                disabled={busy}
                data-testid="save-profile"
                className="mt-6 w-full rounded-xl bg-accent px-6 py-3.5 text-[15px] font-medium text-white transition-all hover:bg-accent-deep disabled:opacity-40"
              >
                {busy ? "Creating…" : "Create account"}
              </button>
            </form>
          )}
        </div>
      </div>
    </main>
  );
}

function ErrorNote({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="alert"
      data-testid="auth-error"
      className="mt-4 rounded-xl bg-danger-wash px-4 py-3 text-[13px] text-danger"
    >
      {children}
    </p>
  );
}

export default function SignInPage() {
  return (
    <Suspense fallback={null}>
      <SignInBody />
    </Suspense>
  );
}
