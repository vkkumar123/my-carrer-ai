"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button, Card, ErrorNote, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { setDevToken } from "@/lib/auth";
import { APP_NAME } from "@/lib/config";
import { devLoginEnabled, getSupabase, googleSignInEnabled } from "@/lib/supabase";

function safeNext(next: string | null) {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 48 48" className="h-5 w-5" aria-hidden>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

function LoginForm() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function google() {
    setError(null);
    const sb = getSupabase();
    if (!sb) return;
    const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`;
    const { error } = await sb.auth.signInWithOAuth({ provider: "google", options: { redirectTo } });
    if (error) setError(error.message);
  }

  async function devLogin(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.devLogin(email, name);
      setDevToken(res.access_token);
      router.push(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
      setBusy(false);
    }
  }

  return (
    <Card className="w-full max-w-sm">
      <h1 className="text-xl font-semibold">Sign in to {APP_NAME}</h1>
      <p className="mt-1 text-sm text-slate-500">Practise real interviews by voice.</p>

      {googleSignInEnabled && (
        <Button variant="secondary" className="mt-6 w-full py-2.5" onClick={google}>
          <GoogleIcon /> Continue with Google
        </Button>
      )}

      {!googleSignInEnabled && !devLoginEnabled && (
        <p className="mt-6 text-sm text-slate-600">Sign-in isn&apos;t configured yet.</p>
      )}

      {devLoginEnabled && (
        <>
          {googleSignInEnabled && (
            <div className="my-5 flex items-center gap-3 text-xs text-slate-400">
              <span className="h-px flex-1 bg-slate-200" /> or, for local development
              <span className="h-px flex-1 bg-slate-200" />
            </div>
          )}
          {!googleSignInEnabled && (
            <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Development sign-in. Google sign-in appears here once Supabase is configured
              (see docs/GOOGLE_SIGN_IN.md).
            </p>
          )}
          <form onSubmit={devLogin} className="mt-4 space-y-3">
            <input className={inputClass} placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} required />
            <input
              className={inputClass}
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Signing in..." : "Continue"}
            </Button>
          </form>
        </>
      )}
      <div className="mt-3">
        <ErrorNote message={error} />
      </div>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <Suspense>
        <LoginForm />
      </Suspense>
    </main>
  );
}
