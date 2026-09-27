"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button, Card, ErrorNote, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { APP_NAME } from "@/lib/config";

function LoginForm() {
  const router = useRouter();
  const next = useSearchParams().get("next") || "/dashboard";
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.devLogin(email, name);
      setToken(res.access_token);
      router.push(next.startsWith("/") ? next : "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
      setBusy(false);
    }
  }

  return (
    <Card className="w-full max-w-sm">
      <h1 className="text-xl font-semibold">Sign in to {APP_NAME}</h1>
      <p className="mt-1 text-sm text-slate-500">
        Development sign-in. Google sign-in via Supabase replaces this in production.
      </p>
      <form onSubmit={submit} className="mt-6 space-y-3">
        <input
          className={inputClass}
          placeholder="Your name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          className={inputClass}
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <ErrorNote message={error} />
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? "Signing in..." : "Continue"}
        </Button>
      </form>
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
