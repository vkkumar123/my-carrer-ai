# My Career AI

Realistic **voice** mock interviews for IT professionals and final-year students.

A candidate picks a **topic** (e.g. "Apache Spark") or a **company loop** (company + role + resume + JD).
The platform plans the technical rounds, and an AI interviewer runs each round **by voice**: it asks
follow-ups, keeps time, and reacts to proctoring (camera on, entire screen shared, fullscreen), much
like a real remote interview. After each round the candidate gets a scored debrief with evidence,
"what a strong answer looks like", and a study plan.

## How it works

```
Browser (Next.js)                         Backend (FastAPI)                  AI
─────────────────                         ─────────────────                  ──
Upload resume / paste JD  ──REST──▶  parse resume + JD, gap map  ──────▶  Claude (smart model)
                                     plan rounds from company blueprint ─▶  Claude (smart model)
Lobby: camera, mic, entire-screen
share, single display, consent
Join round                ──REST──▶  LiveKit token + dispatch agent
   │ WebRTC audio (mic only)
   ▼
LiveKit ◀──────────────▶ Voice agent (LiveKit Agents, Python)
   ▲                        VAD + turn detector ─▶ Deepgram STT ─▶ Claude (fast model) ─▶ Deepgram TTS
   │ data messages:          interview state machine (questions, time, wrap-up)
   │  proctor events, code   reacts to proctoring: warns, pauses on critical issues
   │
Proctoring runs on-device  ──REST──▶  integrity events saved
(MediaPipe face checks,
 tab/fullscreen/screen)               agent posts transcript ─▶ evaluator ─▶ Claude (smart model)
Report page               ◀─REST───  scores, evidence, study plan, integrity score
```

- **Camera and screen video never leave the browser.** They are analysed on-device; only events
  such as "tab switched" or "second person in frame" are sent to the server.
- **Company blueprints** (`services/api/app/blueprints/companies/*.yaml`) describe commonly reported
  round structures and interviewer style. Unknown companies use a generic template. They are labelled
  as typical patterns, not official processes.
- **Cost control:** the high-volume live turns use the fast model, and the few heavy calls
  (planning, evaluation) use the smart model. Background jobs, scale-to-zero hosting.

## Repository layout

| Path | What |
|---|---|
| `apps/web` | Next.js app: setup flow, proctoring lobby, live interview room, reports |
| `services/api` | FastAPI: auth, resumes, loops/rounds, planning + evaluation pipeline, Postgres (Alembic) |
| `services/agent` | LiveKit Agents voice interviewer: state machine, prompts, proctoring reactions |
| `docs/` | [Deployment](docs/DEPLOYMENT.md), [Architecture notes](docs/ARCHITECTURE.md) |
| `docker-compose.yml` | Whole stack locally |

## Run locally

You need API keys for **Anthropic** (Claude) and **Deepgram** (speech-to-text and text-to-speech).

### Option A: Docker Compose

```bash
cp .env.example .env            # add ANTHROPIC_API_KEY and DEEPGRAM_API_KEY
docker compose up --build
```

Open http://localhost:3000 in Chrome or Edge on a laptop or desktop.

The stack uses host ports 3000 (web), 8000 (API), 7880-7882 (LiveKit) and 5433 (Postgres). If
you get "port is already allocated / address already in use", stop whatever uses that port, or
for Postgres set `POSTGRES_HOST_PORT` in `.env` to a free port.

### Option B: run each service

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 22, Postgres 16, and
[`livekit-server`](https://docs.livekit.io/home/self-hosting/local/).

```bash
# 1. LiveKit (dev mode: key "devkey", secret "secret")
livekit-server --dev

# 2. API
cd services/api
cp .env.example .env            # set ANTHROPIC_API_KEY
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# 3. Voice agent
cd services/agent
cp .env.example .env            # set ANTHROPIC_API_KEY and DEEPGRAM_API_KEY
uv sync
uv run python -m interviewer.main download-files
uv run python -m interviewer.main dev

# 4. Web
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

## Tests and checks

```bash
cd services/api   && uv run ruff check . && uv run pytest
cd services/agent && uv run ruff check . && uv run pytest
cd apps/web       && npm run lint && npx tsc --noEmit && npm run build
```

CI runs all of these on every pull request, and also checks that the Alembic migrations apply
cleanly to Postgres (`.github/workflows/ci.yml`).

## Status

MVP in progress. Built so far: resume + JD analysis, company and topic loops, voice interviewer with
timekeeping, proctoring lobby and live monitoring, evaluation reports with an integrity score.

Next up: Supabase Google sign-in (the web app currently uses a development login), payments
(Razorpay), code execution for coding rounds (Judge0), and deployment to staging.
