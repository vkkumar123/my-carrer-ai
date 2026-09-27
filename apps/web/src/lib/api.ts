import { forgetSession, getAccessToken } from "./auth";
import { API_URL } from "./config";
import type { JoinInfo, Level, Loop, ProctorEvent, Resume, Round, User } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = await getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (res.status === 401) {
    forgetSession();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      // Outside React, so no router here; a hard navigation also clears in-memory state.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, msg);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export interface CreateLoopInput {
  mode: "topic" | "company";
  level: Level;
  topic?: string;
  duration_min?: number;
  company?: string;
  role?: string;
  jd_text?: string;
  resume_id?: string;
}

export const api = {
  devLogin: (email: string, name: string) =>
    request<{ access_token: string; user: User }>("/auth/dev-login", {
      method: "POST",
      body: JSON.stringify({ email, name }),
    }),
  me: () => request<User>("/auth/me"),

  listResumes: () => request<Resume[]>("/resumes"),
  uploadResume: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Resume>("/resumes", { method: "POST", body: form });
  },
  deleteResume: (id: string) => request<void>(`/resumes/${id}`, { method: "DELETE" }),

  companies: () => request<{ slug: string; name: string }[]>("/loops/companies"),
  createLoop: (body: CreateLoopInput) =>
    request<Loop>("/loops", { method: "POST", body: JSON.stringify(body) }),
  listLoops: () => request<Loop[]>("/loops"),
  getLoop: (id: string) => request<Loop>(`/loops/${id}`),
  retryLoop: (id: string) => request<Loop>(`/loops/${id}/retry`, { method: "POST" }),
  deleteLoop: (id: string) => request<void>(`/loops/${id}`, { method: "DELETE" }),

  getRound: (id: string) => request<Round>(`/rounds/${id}`),
  joinRound: (id: string) => request<JoinInfo>(`/rounds/${id}/join`, { method: "POST" }),
  retryEvaluation: (id: string) => request<Round>(`/rounds/${id}/evaluate`, { method: "POST" }),
  sendProctorEvents: (id: string, events: ProctorEvent[]) =>
    request<void>(`/rounds/${id}/proctor-events`, {
      method: "POST",
      body: JSON.stringify({ events }),
      keepalive: true,
    }),
};
