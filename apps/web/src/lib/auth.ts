"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getSupabase } from "./supabase";

const KEY = "mca_token";

/** Token from the development login (local only). */
function getDevToken(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setDevToken(token: string) {
  try {
    localStorage.setItem(KEY, token);
  } catch {
    /* storage unavailable */
  }
}

function clearDevToken() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable */
  }
}

/** Current bearer token: the Supabase session (auto-refreshed) or the dev-login token. */
export async function getAccessToken(): Promise<string | null> {
  const sb = getSupabase();
  if (sb) {
    const { data } = await sb.auth.getSession();
    if (data.session) return data.session.access_token;
  }
  return getDevToken();
}

export async function signOut() {
  clearDevToken();
  await getSupabase()?.auth.signOut();
}

/** Clears local credentials after the API rejected them. */
export function forgetSession() {
  clearDevToken();
  void getSupabase()?.auth.signOut({ scope: "local" });
}

/** Redirects to /login when signed out. Returns true once the user is known to be signed in. */
export function useRequireAuth(): boolean {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let alive = true;
    getAccessToken().then((token) => {
      if (!alive) return;
      if (token) setReady(true);
      else router.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
    });
    return () => {
      alive = false;
    };
  }, [router]);
  return ready;
}
