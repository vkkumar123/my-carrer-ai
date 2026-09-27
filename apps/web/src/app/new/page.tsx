"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Page } from "@/components/Nav";
import { Button, Card, ErrorNote, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { Level, Resume } from "@/lib/types";

const LEVELS: { value: Level; label: string }[] = [
  { value: "intern", label: "Intern / final year" },
  { value: "junior", label: "Junior (0-2 yrs)" },
  { value: "mid", label: "Mid (2-5 yrs)" },
  { value: "senior", label: "Senior (5-9 yrs)" },
  { value: "staff", label: "Staff / Lead (9+ yrs)" },
];

export default function NewInterview() {
  const ready = useRequireAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"topic" | "company">("topic");
  const [level, setLevel] = useState<Level>("mid");
  const [topic, setTopic] = useState("");
  const [duration, setDuration] = useState(30);
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [jd, setJd] = useState("");
  const [companies, setCompanies] = useState<{ slug: string; name: string }[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [resumeId, setResumeId] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    api.companies().then(setCompanies, () => {});
    api.listResumes().then((r) => {
      setResumes(r);
      if (r[0]) setResumeId(r[0].id);
    }, () => {});
  }, [ready]);

  async function onUpload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const r = await api.uploadResume(file);
      setResumes((prev) => [r, ...prev]);
      setResumeId(r.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const loop = await api.createLoop(
        mode === "topic"
          ? { mode, level, topic, duration_min: duration, resume_id: resumeId || undefined }
          : { mode, level, company, role, jd_text: jd || undefined, resume_id: resumeId || undefined },
      );
      router.push(`/loops/${loop.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create the interview");
      setBusy(false);
    }
  }

  const selectedResume = resumes.find((r) => r.id === resumeId);

  return (
    <Page>
      <h1 className="text-2xl font-semibold">New interview</h1>
      <form onSubmit={submit} className="mt-6 space-y-6">
        <div className="grid gap-3 sm:grid-cols-2">
          {(
            [
              ["topic", "Topic practice", "One focused voice round on a skill you just learned."],
              ["company", "Company loop", "All technical rounds for a target company and role."],
            ] as const
          ).map(([value, title, body]) => (
            <button
              type="button"
              key={value}
              onClick={() => setMode(value)}
              className={`rounded-2xl p-5 text-left ring-2 transition ${
                mode === value ? "bg-indigo-50 ring-indigo-500" : "bg-white ring-slate-200 hover:ring-slate-300"
              }`}
            >
              <p className="font-medium">{title}</p>
              <p className="mt-1 text-sm text-slate-600">{body}</p>
            </button>
          ))}
        </div>

        <Card className="space-y-4">
          {mode === "topic" ? (
            <div className="grid gap-4 sm:grid-cols-3">
              <label className="sm:col-span-2">
                <span className="text-sm font-medium">Topic</span>
                <input
                  className={`${inputClass} mt-1`}
                  placeholder="e.g. Apache Spark, SQL, React, Kubernetes"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  required
                />
              </label>
              <label>
                <span className="text-sm font-medium">Duration</span>
                <select
                  className={`${inputClass} mt-1`}
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                >
                  {[15, 20, 30, 45].map((m) => (
                    <option key={m} value={m}>
                      {m} minutes
                    </option>
                  ))}
                </select>
              </label>
            </div>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <label>
                  <span className="text-sm font-medium">Company</span>
                  <input
                    className={`${inputClass} mt-1`}
                    list="companies"
                    placeholder="e.g. Adobe"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    required
                  />
                  <datalist id="companies">
                    {companies.map((c) => (
                      <option key={c.slug} value={c.name} />
                    ))}
                  </datalist>
                </label>
                <label>
                  <span className="text-sm font-medium">Role</span>
                  <input
                    className={`${inputClass} mt-1`}
                    placeholder="e.g. Senior Data Engineer"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    required
                  />
                </label>
              </div>
              <label className="block">
                <span className="text-sm font-medium">Job description</span>
                <textarea
                  className={`${inputClass} mt-1 h-40`}
                  placeholder="Paste the job description here (recommended)"
                  value={jd}
                  onChange={(e) => setJd(e.target.value)}
                  maxLength={30000}
                />
              </label>
            </>
          )}

          <label className="block">
            <span className="text-sm font-medium">Experience level</span>
            <select
              className={`${inputClass} mt-1`}
              value={level}
              onChange={(e) => setLevel(e.target.value as Level)}
            >
              {LEVELS.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>

          <div>
            <span className="text-sm font-medium">
              Resume {mode === "company" ? "(recommended)" : "(optional)"}
            </span>
            <div className="mt-1 flex flex-wrap items-center gap-3">
              {resumes.length > 0 && (
                <select
                  className={`${inputClass} max-w-xs`}
                  value={resumeId}
                  onChange={(e) => setResumeId(e.target.value)}
                >
                  <option value="">No resume</option>
                  {resumes.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.filename}
                    </option>
                  ))}
                </select>
              )}
              <label className="cursor-pointer rounded-lg px-3 py-2 text-sm font-medium text-indigo-700 ring-1 ring-indigo-200 hover:bg-indigo-50">
                {uploading ? "Reading resume..." : "Upload PDF"}
                <input
                  type="file"
                  accept=".pdf,.txt"
                  className="hidden"
                  disabled={uploading}
                  onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
                />
              </label>
            </div>
            {selectedResume?.parsed?.headline && (
              <p className="mt-2 text-sm text-slate-600">
                Read as: <span className="font-medium">{selectedResume.parsed.headline}</span>
              </p>
            )}
          </div>
        </Card>

        <ErrorNote message={error} />
        <Button type="submit" disabled={busy || uploading}>
          {busy ? "Creating..." : "Prepare my interview"}
        </Button>
      </form>
    </Page>
  );
}
