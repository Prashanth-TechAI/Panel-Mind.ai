"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { API_BASE } from "@/lib/api";
import { authFetch, getToken, useAuth } from "@/lib/auth";

/**
 * Broadcast when the aspirant changes their photograph.
 *
 * The header and the profile page are not related, so a new photo would
 * otherwise sit behind an unchanged `src` until a full reload. Everything that
 * shows the avatar listens for this and re-requests it.
 */
export const AVATAR_CHANGED = "panelmind:avatar-changed";

/**
 * The application bar.
 *
 * On the landing page it starts bare and, once the reader scrolls, lifts off
 * the page as a floating capsule — so it reads as a control surface over the
 * content rather than a band welded to the top of it. The logo never hides:
 * a visitor has to know whose page this is at first paint.
 */

const NAV = [
  { href: "/", label: "Home" },
  { href: "/#how", label: "How it works" },
  { href: "/#proof", label: "Aspirants" },
  { href: "/#faq", label: "FAQ" },
  { href: "/contact", label: "Contact" },
];

const MENU = [
  { href: "/me", label: "My profile" },
  { href: "/me/daf", label: "Your DAF" },
  { href: "/mocks", label: "My mocks" },
  { href: "/progress", label: "My progress" },
  { href: "/plan", label: "My plan" },
  { href: "/daf", label: "New mock" },
  { href: "/contact", label: "Help & support" },
];

/** Far enough down that the lift reads as intent, not as a twitch. */
const LIFT_AFTER_PX = 24;

export function AppHeader({
  /**
   * Landing pages open on the headline, so the bar's chrome would compete
   * with it. Only the chrome fades in — never the logo.
   */
  transparentUntilScrolled = false,
}: {
  transparentUntilScrolled?: boolean;
}) {
  const { account, loading, signOut } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [dafHint, setDafHint] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  // Bumped when the photograph changes, and used to bust the image cache.
  // `broken` covers the case where the account claims a photo the server
  // cannot serve — the initials come back rather than a broken image icon.
  const [avatarStamp, setAvatarStamp] = useState(0);
  const [broken, setBroken] = useState(false);

  useEffect(() => setOpen(false), [pathname]);

  useEffect(() => {
    const onChanged = () => {
      setBroken(false);
      setAvatarStamp(Date.now());
    };
    window.addEventListener(AVATAR_CHANGED, onChanged);
    return () => window.removeEventListener(AVATAR_CHANGED, onChanged);
  }, []);

  /**
   * Tell the aspirant, in the menu itself, whether the board has their form —
   * uploaded, typed, or still missing. It is the first thing they need before
   * anything else in the product works.
   */
  useEffect(() => {
    if (!account) return;
    authFetch("/api/me/daf")
      .then((r) => (r.ok ? r.json() : null))
      .then((body) => {
        if (!body?.has_daf) return setDafHint("Not given yet");
        setDafHint(body.source === "upload" ? "Uploaded as PDF" : "Entered by form");
      })
      .catch(() => setDafHint("Not given yet"));
  }, [account]);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Scroll position is state that lives outside React, so read it as an
  // external store rather than mirroring it into an effect. This also reads
  // correctly on back-navigation, where the browser restores scroll before
  // any effect would have run.
  const subscribe = useCallback(
    (onChange: () => void) => {
      if (!transparentUntilScrolled) return () => {};
      window.addEventListener("scroll", onChange, { passive: true });
      return () => window.removeEventListener("scroll", onChange);
    },
    [transparentUntilScrolled],
  );
  const getSnapshot = useCallback(
    () => !transparentUntilScrolled || window.scrollY > LIFT_AFTER_PX,
    [transparentUntilScrolled],
  );
  const lifted = useSyncExternalStore(
    subscribe,
    getSnapshot,
    () => !transparentUntilScrolled,
  );

  // The browser fetches this itself and sends no Authorization header, so the
  // token rides in the query string — the same arrangement the DAF file uses.
  const avatarUrl =
    account?.has_avatar && !broken
      ? `${API_BASE}/api/me/avatar?token=${encodeURIComponent(getToken() ?? "")}&v=${avatarStamp}`
      : null;

  /** The photograph where there is one, the initials where there is not. */
  const Avatar = ({ size }: { size: string }) =>
    avatarUrl ? (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={avatarUrl}
        alt=""
        data-testid="header-avatar"
        onError={() => setBroken(true)}
        className={`${size} shrink-0 rounded-full object-cover`}
      />
    ) : (
      <span
        data-testid="header-initials"
        className={`${size} grid shrink-0 place-items-center rounded-full bg-white/15 text-[13px] font-semibold`}
      >
        {account?.initials}
      </span>
    );

  return (
    <header
      className={`${transparentUntilScrolled ? "fixed inset-x-0" : "sticky"} top-0 z-50 px-3 pt-3 sm:px-5 sm:pt-4`}
    >
      <div
        className={`mx-auto flex h-[68px] w-full max-w-[1400px] items-center gap-6 rounded-full pr-3 pl-5 transition-all duration-300 ease-out sm:pr-4 sm:pl-7 motion-reduce:transition-none ${
          lifted
            ? "border border-line bg-surface/90 shadow-lift backdrop-blur-xl"
            : "border border-transparent bg-transparent"
        }`}
      >
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2.5"
          aria-label="PanelMind AI home"
        >
          {/* Natural aspect (≈1.2:1) — a square box letterboxes the mark. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo-mark.svg"
            alt=""
            width={53}
            height={44}
            className="h-11 w-auto shrink-0"
          />
          <span className="font-display text-[21px] leading-none font-bold tracking-[-0.015em] text-ink">
            PanelMind <span className="text-accent-bright">AI</span>
          </span>
        </Link>

        <nav className="hidden flex-1 items-center justify-center gap-7 lg:flex">
          {NAV.map((item) => {
            // In-page anchors are never "active" by pathname — every one of
            // them starts with "/", so a startsWith check lights them all up.
            const active = item.href.includes("#")
              ? false
              : item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.label}
                href={item.href}
                className="group relative text-[15px] font-medium text-ink-soft transition-colors hover:text-ink"
              >
                {item.label}
                {/* Brass underline: the one place the board's own colour shows. */}
                <span
                  aria-hidden
                  className={`absolute -bottom-1.5 left-0 h-[2px] rounded-full bg-brass transition-all duration-200 ${
                    active ? "w-full" : "w-0 group-hover:w-full"
                  }`}
                />
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex shrink-0 items-center gap-2 lg:ml-0">
          {!loading && !account && (
            <>
              <Link
                href="/signin"
                data-testid="header-signin"
                className="hidden rounded-full px-4 py-2.5 text-[15px] font-medium text-ink-soft transition-colors hover:text-ink sm:block"
              >
                Sign in
              </Link>
              <Link
                href="/daf"
                className="rounded-full bg-accent px-6 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-accent-deep"
              >
                Sit a mock
              </Link>
            </>
          )}

          {account && (
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={open}
                data-testid="profile-button"
                className="flex items-center gap-2.5 rounded-full bg-accent py-1.5 pr-4 pl-1.5 text-white transition-colors hover:bg-accent-deep"
              >
                <Avatar size="size-9" />
                <span className="max-w-[9rem] truncate text-[15px] font-semibold">
                  {account.name?.split(" ")[0] || "Account"}
                </span>
                <svg
                  width="11"
                  height="7"
                  viewBox="0 0 10 6"
                  fill="none"
                  aria-hidden
                  className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}
                >
                  <path
                    d="M1 1l4 4 4-4"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>

              {open && (
                <div
                  role="menu"
                  data-testid="profile-menu"
                  className="animate-pop absolute right-0 mt-3 w-[248px] overflow-hidden rounded-2xl border border-line bg-surface shadow-pop"
                >
                  <div className="border-b border-line px-5 py-4">
                    <div className="flex items-center gap-3">
                      {/* Dark-on-light here, so the initials need the accent
                          rather than the button's translucent white. */}
                      <span className="grid size-11 shrink-0 place-items-center overflow-hidden rounded-full bg-accent text-[14px] font-semibold text-white">
                        {avatarUrl ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={avatarUrl}
                            alt=""
                            data-testid="menu-avatar"
                            onError={() => setBroken(true)}
                            className="size-full object-cover"
                          />
                        ) : (
                          account.initials
                        )}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-[15px] font-semibold text-ink">
                          {account.name || "Your account"}
                        </p>
                        <p className="mt-0.5 truncate text-[13px] text-ink-soft">
                          {account.email || account.phone}
                        </p>
                      </div>
                    </div>
                    {dafHint && (
                      <p className="mt-2.5 inline-flex items-center gap-1.5 rounded-full bg-surface-sunk px-2.5 py-1 text-[12px] font-medium text-ink-soft">
                        <span
                          aria-hidden
                          className="size-1.5 rounded-full"
                          style={{
                            background:
                              dafHint === "Not given yet"
                                ? "var(--color-warn)"
                                : "var(--color-good)",
                          }}
                        />
                        DAF · {dafHint}
                      </p>
                    )}
                  </div>

                  <div className="py-2">
                    {MENU.map((item) => (
                      <Link
                        key={item.href}
                        href={item.href}
                        role="menuitem"
                        data-testid={`menu-${item.href.slice(1)}`}
                        className="block px-5 py-2.5 text-[15px] text-ink transition-colors hover:bg-surface-sunk"
                      >
                        {item.label}
                      </Link>
                    ))}
                  </div>

                  <div className="border-t border-line py-2">
                    <button
                      type="button"
                      role="menuitem"
                      data-testid="sign-out"
                      onClick={() => {
                        signOut();
                        router.push("/");
                      }}
                      className="block w-full px-5 py-2.5 text-left text-[15px] text-ink-soft transition-colors hover:bg-surface-sunk hover:text-danger"
                    >
                      Log out
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
