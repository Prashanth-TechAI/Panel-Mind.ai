"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppHeader, AVATAR_CHANGED } from "@/components/AppHeader";
import { SiteFooter } from "@/components/SiteFooter";
import { API_BASE } from "@/lib/api";
import { authFetch, getToken, useAuth, type Account } from "@/lib/auth";

/**
 * Your profile.
 *
 * Three rules held this page together:
 *
 *   1. A contact is verified only when a code sent to it came back correct.
 *      The channel used to sign in is verified by that act; the other one is
 *      typed in afterwards and nobody has proved it works, so it says so and
 *      offers to prove it in one click.
 *   2. Awards are earned from the record — interviews sat, marks awarded,
 *      answers judged. Nothing is granted for turning up.
 *   3. No control claims something the server did not do. The WhatsApp switch
 *      stores a real preference and reports honestly whether a message could
 *      actually be sent from this deployment.
 */

interface Award {
  key: string;
  title: string;
  detail: string;
  held: boolean;
  progress: string;
}

interface Profile {
  user: Account;
  held: number;
  total: number;
  awards: Award[];
  stats: {
    mocks: number;
    completed: number;
    best_marks: number | null;
    average_marks: number | null;
    answers_given: number;
    first_at: number | null;
    last_at: number | null;
  };
  whatsapp: {
    opt_in: boolean;
    sending_configured: boolean;
    business_number: string;
    link: string | null;
  };
}

const field =
  "mt-1.5 w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-[15px] text-ink outline-none transition-all placeholder:text-ink-faint focus:border-accent focus:ring-4 focus:ring-accent/10";

export default function ProfilePage() {
  const router = useRouter();
  const { account, loading, refresh } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(true);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Which contact is mid-verification, and the code being typed for it.
  const [verifying, setVerifying] = useState<"phone" | "email" | null>(null);
  const [code, setCode] = useState("");
  const [codeNote, setCodeNote] = useState<string | null>(null);
  const [waBusy, setWaBusy] = useState(false);
  const [waNote, setWaNote] = useState<string | null>(null);
  const [avatarStamp, setAvatarStamp] = useState(0);
  const photoRef = useRef<HTMLInputElement | null>(null);

  const load = useCallback(async () => {
    const res = await authFetch("/api/me/profile");
    if (!res.ok) return setBusy(false);
    const data = (await res.json()) as Profile;
    setProfile(data);
    setName(data.user.name ?? "");
    setEmail(data.user.email ?? "");
    setPhone(data.user.phone ?? "");
    setBusy(false);
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!account) router.replace("/signin?next=/me");
    else void load();
  }, [account, loading, router, load]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const res = await authFetch("/api/me/profile", {
        method: "PATCH",
        body: JSON.stringify({ name, email, phone }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.error ?? body?.detail?.[0]?.msg ?? "That did not save.");
      setSaved(true);
      await Promise.all([load(), refresh()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That did not save.");
    } finally {
      setSaving(false);
    }
  }

  /** Send a code to whichever contact is not yet proved. */
  async function startVerify(channel: "phone" | "email") {
    setError(null);
    setCode("");
    setCodeNote(null);
    setVerifying(channel);
    try {
      const res = await authFetch("/api/me/verify/start", {
        method: "POST",
        body: JSON.stringify({ channel }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body?.error ?? "The code could not be sent.");

      // In development the code is returned rather than delivered. Filling it
      // in beats making someone read it out of a server log.
      if (body.dev_code) {
        setCode(body.dev_code);
        setCodeNote(`Development code ${body.dev_code} — filled in for you.`);
      } else {
        setCodeNote(`Code sent to ${body.destination}.`);
      }
    } catch (err) {
      setVerifying(null);
      setError(err instanceof Error ? err.message : "The code could not be sent.");
    }
  }

  async function confirmVerify() {
    if (!verifying) return;
    setError(null);
    try {
      const res = await authFetch("/api/me/verify/confirm", {
        method: "POST",
        body: JSON.stringify({ channel: verifying, code }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body?.error ?? "That code is not right.");
      setVerifying(null);
      setCode("");
      setCodeNote(null);
      await Promise.all([load(), refresh()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That code is not right.");
    }
  }

  async function toggleWhatsapp(next: boolean) {
    setWaBusy(true);
    setWaNote(null);
    setError(null);
    try {
      const res = await authFetch("/api/me/whatsapp", {
        method: "PUT",
        body: JSON.stringify({ opt_in: next }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body?.error ?? "That could not be changed.");

      // Say exactly what happened. A switch that flips green while nothing was
      // sent is the thing this page must never do.
      if (!next) setWaNote("Updates on WhatsApp are off.");
      else if (body.confirmation?.sent)
        setWaNote("Confirmation sent — check WhatsApp.");
      else
        setWaNote(
          "Saved. This deployment has no WhatsApp sender configured yet, " +
            "so nothing has been sent to you.",
        );
      await Promise.all([load(), refresh()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That could not be changed.");
    } finally {
      setWaBusy(false);
    }
  }

  async function uploadPhoto(file: File) {
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await authFetch("/api/me/avatar", { method: "POST", body });
      if (!res.ok) {
        const b = await res.json().catch(() => null);
        throw new Error(b?.error ?? "That photograph could not be saved.");
      }
      setAvatarStamp(Date.now());
      await Promise.all([load(), refresh()]);
      // The header shows the same photograph and has no other way to know.
      window.dispatchEvent(new Event(AVATAR_CHANGED));
    } catch (err) {
      setError(err instanceof Error ? err.message : "That photograph could not be saved.");
    }
  }

  if (loading || busy) {
    return (
      <>
        <AppHeader />
        <main className="flex-1 px-6 py-24 text-center text-[15px] text-ink-faint">
          Fetching your profile…
        </main>
        <SiteFooter />
      </>
    );
  }

  const u = profile?.user;
  const token = getToken() ?? "";
  const avatarUrl = u?.has_avatar
    ? `${API_BASE}/api/me/avatar?token=${encodeURIComponent(token)}&v=${avatarStamp}`
    : null;
  const stats = profile?.stats;

  return (
    <>
      <AppHeader />
      <main className="mx-auto w-full max-w-[1180px] flex-1 px-6 py-12 sm:px-10">
        {/* --- Identity --- */}
        <section className="card flex flex-wrap items-center gap-7 p-7 sm:p-9">
          <div className="relative shrink-0">
            {avatarUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={avatarUrl}
                alt=""
                data-testid="avatar-image"
                className="size-24 rounded-2xl border border-line object-cover"
              />
            ) : (
              <span
                data-testid="avatar-initials"
                className="grid size-24 place-items-center rounded-2xl bg-accent text-[30px] font-bold text-white"
              >
                {u?.initials ?? "?"}
              </span>
            )}
            <input
              ref={photoRef}
              type="file"
              accept="image/*"
              data-testid="avatar-file"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void uploadPhoto(f);
              }}
            />
            <button
              type="button"
              onClick={() => photoRef.current?.click()}
              data-testid="avatar-change"
              className="absolute -right-2 -bottom-2 rounded-full border border-line bg-surface px-3 py-1.5 text-[12px] font-semibold text-ink shadow-pop transition-colors hover:bg-surface-sunk"
            >
              {u?.has_avatar ? "Change" : "Add photo"}
            </button>
          </div>

          <div className="min-w-[14rem] flex-1">
            <h1 className="text-[30px] font-bold tracking-[-0.03em]">
              {u?.name || "Your account"}
            </h1>
            <p className="mt-1.5 text-[15px] text-ink-soft">
              {stats?.mocks
                ? `${stats.mocks} board${stats.mocks === 1 ? "" : "s"} sat` +
                  (stats.best_marks ? ` · best ${stats.best_marks}/275` : "")
                : "No boards sat yet"}
            </p>
            <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-surface-sunk px-3 py-1.5 text-[13px] font-medium text-ink-soft">
              <span
                aria-hidden
                className="size-1.5 rounded-full"
                style={{ background: "var(--color-good)" }}
              />
              {profile?.held} of {profile?.total} awards earned
            </p>
          </div>
        </section>

        {error && (
          <p role="alert" data-testid="profile-error"
             className="mt-6 rounded-xl bg-danger-wash px-5 py-3.5 text-[14px] text-danger">
            {error}
          </p>
        )}

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.15fr_1fr]">
          {/* --- Details, and proving them --- */}
          <section className="card p-7 sm:p-9">
            <h2 className="text-[21px] font-semibold">Your details</h2>
            <p className="mt-1.5 text-[14px] leading-relaxed text-ink-soft">
              Either contact signs you in. A verified one also receives your
              results.
            </p>

            <form onSubmit={save} data-testid="profile-form" className="mt-7 space-y-5">
              <label className="block">
                <span className="text-[13px] font-medium text-ink">Full name</span>
                <input
                  name="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className={field}
                  required
                  minLength={2}
                />
              </label>

              {(
                [
                  {
                    channel: "email" as const,
                    label: "Email",
                    value: email,
                    set: setEmail,
                    verified: u?.email_verified,
                    type: "email",
                    placeholder: "you@example.com",
                  },
                  {
                    channel: "phone" as const,
                    label: "Mobile number",
                    value: phone,
                    set: setPhone,
                    verified: u?.phone_verified,
                    type: "tel",
                    placeholder: "9876543210",
                  },
                ]
              ).map((row) => (
                <div key={row.channel}>
                  <span className="flex items-center gap-2">
                    <span className="text-[13px] font-medium text-ink">{row.label}</span>
                    {row.value ? (
                      row.verified ? (
                        <span
                          data-testid={`${row.channel}-verified`}
                          className="inline-flex items-center gap-1 rounded-full bg-good-wash px-2 py-0.5 text-[11px] font-semibold text-good"
                        >
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
                               stroke="currentColor" strokeWidth="3.5" strokeLinecap="round"
                               strokeLinejoin="round" aria-hidden>
                            <path d="M20 6L9 17l-5-5" />
                          </svg>
                          Verified
                        </span>
                      ) : (
                        <span
                          data-testid={`${row.channel}-unverified`}
                          className="rounded-full bg-warn-wash px-2 py-0.5 text-[11px] font-semibold text-warn"
                        >
                          Not verified
                        </span>
                      )
                    ) : null}
                  </span>

                  <div className="flex flex-wrap items-center gap-2.5">
                    <input
                      name={row.channel}
                      type={row.type}
                      value={row.value}
                      onChange={(e) => row.set(e.target.value)}
                      placeholder={row.placeholder}
                      className={`${field} min-w-[12rem] flex-1`}
                    />
                    {row.value && !row.verified && verifying !== row.channel && (
                      <button
                        type="button"
                        onClick={() => void startVerify(row.channel)}
                        data-testid={`verify-${row.channel}`}
                        className="mt-1.5 shrink-0 rounded-full bg-accent px-5 py-2.5 text-[14px] font-semibold text-white transition-colors hover:bg-accent-deep"
                      >
                        Verify
                      </button>
                    )}
                  </div>

                  {verifying === row.channel && (
                    <div
                      data-testid={`verify-panel-${row.channel}`}
                      className="mt-3 rounded-xl border border-line bg-surface-sunk p-4"
                    >
                      {codeNote && (
                        <p className="mb-2.5 text-[13px] text-ink-soft">{codeNote}</p>
                      )}
                      <div className="flex flex-wrap items-center gap-2.5">
                        <input
                          value={code}
                          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                          inputMode="numeric"
                          maxLength={6}
                          placeholder="6-digit code"
                          data-testid={`code-${row.channel}`}
                          className="w-[9rem] rounded-xl border border-line bg-surface px-3.5 py-2.5 text-center text-[16px] tracking-[0.3em] outline-none focus:border-accent"
                        />
                        <button
                          type="button"
                          onClick={() => void confirmVerify()}
                          disabled={code.length !== 6}
                          data-testid={`confirm-${row.channel}`}
                          className="rounded-full bg-accent px-5 py-2.5 text-[14px] font-semibold text-white transition-colors hover:bg-accent-deep disabled:opacity-50"
                        >
                          Confirm
                        </button>
                        <button
                          type="button"
                          onClick={() => setVerifying(null)}
                          className="text-[14px] font-medium text-ink-soft hover:text-ink"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}

              <div className="flex flex-wrap items-center gap-4 pt-1">
                <button
                  type="submit"
                  disabled={saving}
                  data-testid="profile-save"
                  className="rounded-full bg-accent px-7 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-accent-deep disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Save changes"}
                </button>
                {saved && (
                  <span data-testid="profile-saved" className="text-[14px] font-medium text-good">
                    Saved
                  </span>
                )}
              </div>
            </form>

            {/* --- WhatsApp --- */}
            <div className="mt-9 border-t border-line pt-7">
              <div className="flex flex-wrap items-start justify-between gap-5">
                <div className="min-w-[14rem] flex-1">
                  <h3 className="text-[17px] font-semibold">Updates on WhatsApp</h3>
                  <p className="mt-1.5 text-[14px] leading-relaxed text-ink-soft">
                    Your board&rsquo;s verdict and your marks, sent to{" "}
                    {u?.phone || "your mobile"} as soon as they are ready.
                  </p>
                </div>

                <button
                  type="button"
                  role="switch"
                  aria-checked={profile?.whatsapp.opt_in ?? false}
                  disabled={waBusy || !u?.phone_verified}
                  onClick={() => void toggleWhatsapp(!profile?.whatsapp.opt_in)}
                  data-testid="whatsapp-toggle"
                  className={`relative mt-1 h-8 w-14 shrink-0 rounded-full transition-colors disabled:opacity-40 ${
                    profile?.whatsapp.opt_in ? "bg-good" : "bg-line"
                  }`}
                >
                  <span
                    className={`absolute top-1 size-6 rounded-full bg-surface shadow-pop transition-all ${
                      profile?.whatsapp.opt_in ? "left-7" : "left-1"
                    }`}
                  />
                </button>
              </div>

              {!u?.phone_verified && (
                <p data-testid="whatsapp-blocked" className="mt-3 text-[13px] text-ink-soft">
                  Verify your mobile number above to switch this on. We do not
                  message a number nobody has proved they hold.
                </p>
              )}

              {waNote && (
                <p data-testid="whatsapp-note" className="mt-3 text-[13px] text-ink-soft">
                  {waNote}
                </p>
              )}

              {profile?.whatsapp.link && (
                <a
                  href={profile.whatsapp.link}
                  target="_blank"
                  rel="noreferrer"
                  data-testid="whatsapp-link"
                  className="mt-3 inline-block text-[14px] font-semibold text-accent hover:underline"
                >
                  Open the chat and send the first message
                </a>
              )}
            </div>
          </section>

          {/* --- Awards --- */}
          <section className="card p-7 sm:p-9">
            <h2 className="text-[21px] font-semibold">Awards</h2>
            <p className="mt-1.5 text-[14px] leading-relaxed text-ink-soft">
              Earned from the record — interviews sat, marks awarded, answers
              judged. None of them are given for signing up.
            </p>

            {stats && (
              <dl className="mt-7 grid grid-cols-2 gap-4 sm:grid-cols-4">
                {[
                  { label: "Boards sat", value: stats.mocks },
                  { label: "Completed", value: stats.completed },
                  { label: "Best marks", value: stats.best_marks ?? "—" },
                  { label: "Answers given", value: stats.answers_given },
                ].map((s) => (
                  <div key={s.label} className="rounded-xl bg-surface-sunk px-4 py-3.5">
                    <dt className="text-[12px] font-medium text-ink-soft">{s.label}</dt>
                    <dd className="mt-0.5 text-[22px] font-bold tabular-nums">{s.value}</dd>
                  </div>
                ))}
              </dl>
            )}

            <ul className="mt-7 space-y-3" data-testid="awards">
              {profile?.awards.map((a) => (
                <li
                  key={a.key}
                  data-testid={`award-${a.key}`}
                  data-held={a.held}
                  className={`flex items-start gap-3.5 rounded-xl border px-4 py-3.5 ${
                    a.held ? "border-good/30 bg-good-wash" : "border-line bg-surface"
                  }`}
                >
                  <span
                    aria-hidden
                    className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full ${
                      a.held ? "bg-good text-white" : "border border-line text-ink-faint"
                    }`}
                  >
                    {a.held ? (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                           stroke="currentColor" strokeWidth="3.5" strokeLinecap="round"
                           strokeLinejoin="round">
                        <path d="M20 6L9 17l-5-5" />
                      </svg>
                    ) : null}
                  </span>
                  <div>
                    <p className={`text-[15px] font-semibold ${a.held ? "text-ink" : "text-ink-soft"}`}>
                      {a.title}
                    </p>
                    <p className="mt-0.5 text-[13px] leading-relaxed text-ink-soft">
                      {a.held ? a.detail : a.progress || a.detail}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
