"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ErrorNote, LinkButton, Spinner } from "@/components/ui";
import { getSupabase } from "@/lib/supabase";

/** Google redirects here; the Supabase client exchanges the ?code for a session. */
export default function AuthCallback() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const next = params.get("next");
    const target = next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
    const sb = getSupabase();
    if (!sb) {
      router.replace("/login");
      return;
    }
    // getSession waits for the client to finish exchanging the code from the URL.
    sb.auth.getSession().then(({ data, error }) => {
      if (data.session) router.replace(target);
      else setError(error?.message ?? params.get("error_description") ?? "Sign-in failed. Please try again.");
    });
  }, [router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4">
      {error ? (
        <>
          <ErrorNote message={error} />
          <LinkButton href="/login" variant="secondary">
            Back to sign in
          </LinkButton>
        </>
      ) : (
        <Spinner className="text-indigo-600" />
      )}
    </main>
  );
}
