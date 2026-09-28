"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { API_BASE } from "@/lib/api";

/**
 * Client-side session.
 *
 * The token is opaque and lives in localStorage; every authenticated request
 * goes through `authFetch` so there is exactly one place that knows how a
 * request is signed.
 */

export const TOKEN_KEY = "panelmind.token";

export interface Account {
  id: string;
  phone: string;
  name: string;
  email: string;
  initials: string;
  is_complete: boolean;
  mocks_taken: number;
  created_at: number;
  /** A contact is verified only once a code sent to it came back correct. */
  email_verified: boolean;
  phone_verified: boolean;
  whatsapp_opt_in: boolean;
  has_avatar: boolean;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken();

  // FormData must set its own Content-Type — the browser appends the multipart
  // boundary, and overriding it with application/json makes the body
  // unparseable. That is a 422 before the handler is ever reached.
  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;

  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.body && !isFormData ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
}

/** Throws a human-readable message rather than a status code. */
export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await authFetch(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const payload = await res.json().catch(() => null);

  if (!res.ok) {
    const detail = payload?.detail ?? payload?.error;
    const message = Array.isArray(detail)
      ? (detail[0]?.msg ?? "That did not work.")
      : (detail ?? "That did not work.");
    throw new Error(String(message).replace(/^Value error, /, ""));
  }

  return payload as T;
}

interface AuthState {
  account: Account | null;
  loading: boolean;
  signOut: () => void;
  refresh: () => Promise<void>;
  adopt: (token: string, account: Account) => void;
}

const AuthContext = createContext<AuthState>({
  account: null,
  loading: true,
  signOut: () => {},
  refresh: async () => {},
  adopt: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setAccount(null);
      setLoading(false);
      return;
    }
    try {
      const res = await authFetch("/api/auth/me");
      if (!res.ok) throw new Error("session expired");
      const { user } = await res.json();
      setAccount(user as Account);
    } catch {
      clearToken();
      setAccount(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signOut = useCallback(() => {
    clearToken();
    setAccount(null);
  }, []);

  const adopt = useCallback((token: string, next: Account) => {
    setToken(token);
    setAccount(next);
    setLoading(false);
  }, []);

  const value = useMemo(
    () => ({ account, loading, signOut, refresh, adopt }),
    [account, loading, signOut, refresh, adopt],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}

export interface UploadResult<T> {
  ok: boolean;
  status: number;
  data: T | null;
}

/**
 * Upload with real progress.
 *
 * `fetch` cannot report how much of a request body has gone out, so this drops
 * to XHR — the only way to show a percentage that is actually true. Note the
 * percentage covers the *transfer* only; what the server does afterwards has
 * no progress feed, and the caller is expected to stop claiming a number once
 * `onProgress` reaches 1.
 */
export function authUpload<T>(
  path: string,
  body: FormData,
  onProgress: (fraction: number) => void,
): Promise<UploadResult<T>> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}${path}`);

    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    });
    xhr.upload.addEventListener("load", () => onProgress(1));

    xhr.addEventListener("load", () => {
      let data: T | null = null;
      try {
        data = JSON.parse(xhr.responseText) as T;
      } catch {
        // A non-JSON body is handled by the caller via `ok`.
      }
      resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, data });
    });
    xhr.addEventListener("error", () =>
      reject(new Error("The upload failed. Check your connection and try again.")),
    );
    xhr.addEventListener("abort", () => reject(new Error("The upload was cancelled.")));

    xhr.send(body);
  });
}
