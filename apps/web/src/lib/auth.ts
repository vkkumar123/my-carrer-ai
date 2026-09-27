"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const KEY = "mca_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string) {
  try {
    localStorage.setItem(KEY, token);
  } catch {
    /* storage unavailable */
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable */
  }
}

/** Redirects to /login when there is no token. Returns true once the user is known to be signed in. */
export function useRequireAuth(): boolean {
  const router = useRouter();
  const [ready] = useState(() => typeof window !== "undefined" && !!getToken());
  useEffect(() => {
    if (!ready) router.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
  }, [ready, router]);
  return ready;
}
