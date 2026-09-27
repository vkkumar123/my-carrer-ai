import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
// Supabase calls this the "publishable" (formerly "anon") key. It is safe to expose.
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let client: SupabaseClient | null = null;

/** Supabase client for Google sign-in, or null when Supabase isn't configured. */
export function getSupabase(): SupabaseClient | null {
  if (!url || !key || typeof window === "undefined") return null;
  client ??= createClient(url, key, {
    auth: { flowType: "pkce", persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  });
  return client;
}

export const googleSignInEnabled = Boolean(url && key);
export const devLoginEnabled = process.env.NEXT_PUBLIC_DEV_LOGIN !== "false";
