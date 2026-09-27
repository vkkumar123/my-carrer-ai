"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { clearToken } from "@/lib/auth";
import { APP_NAME } from "@/lib/config";

export function Nav() {
  const router = useRouter();
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <Link href="/dashboard" className="font-semibold text-slate-900">
          {APP_NAME}
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          <Link href="/dashboard" className="rounded-lg px-3 py-1.5 text-slate-600 hover:bg-slate-100">
            Dashboard
          </Link>
          <Link href="/new" className="rounded-lg px-3 py-1.5 text-slate-600 hover:bg-slate-100">
            New interview
          </Link>
          <button
            onClick={() => {
              clearToken();
              router.push("/login");
            }}
            className="rounded-lg px-3 py-1.5 text-slate-600 hover:bg-slate-100"
          >
            Sign out
          </button>
        </nav>
      </div>
    </header>
  );
}

export function Page({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Nav />
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
    </>
  );
}
