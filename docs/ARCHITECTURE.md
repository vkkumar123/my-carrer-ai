# Architecture notes

## Data model

- `users`: created from the Supabase JWT on first request (or `/auth/dev-login` locally). See
  [Google sign-in setup](GOOGLE_SIGN_IN.md).
- `resumes`: original file in storage, extracted text, and a parsed profile (JSON).
- `interview_loops`: one practice session. `mode` is `topic` or `company`; `spec` holds the
  blueprint output (persona, round list, disclaimer); `jd_parsed` and `gap_map` come from the LLM.
- `rounds`: one per interview round. `plan` (questions + rubric) stays hidden from the candidate
  until the round ends. Holds the transcript, final code and whiteboard, the interviewer's
  notes (hints used), the evaluation and the integrity summary.
- `proctor_events`: integrity events reported by the browser during a round.

Round status: `pending -> in_progress -> completed -> evaluated`, or `insufficient` (too short to
grade) or `eval_failed` (retryable). An agent failure before the candidate answered anything returns
the round to `pending` so it isn't lost.

## AI calls

| Job | Where | Model |
|---|---|---|
| Parse resume, parse JD | API, on upload / loop creation | smart, low effort |
| Gap map (resume vs JD) | API background job | smart |
| Plan rounds (questions, follow-ups, rubric) | API background job | smart, high effort |
| Live interviewer turns | Agent, per candidate turn | fast |
| Evaluate round | API background job after the round | smart, high effort |

The API uses structured outputs (Pydantic schemas in `services/api/app/llm/schemas.py`), so every
response is validated. Models are set by `LLM_MODEL_SMART` / `LLM_MODEL_FAST`.

## Questions and the candidate's workspace

Each planned question has:

- `prompt`: what the interviewer says (1-2 sentences, one ask)
- `screen_text`: what the problem panel shows (schemas, sample data, requirements)
- `workspace`: `code`, `whiteboard` or `none`, plus a `language` for code
- `follow_ups`, and progressive `hints`

The live room always has a code editor (Monaco) and a whiteboard (Excalidraw). The right one
opens for each question. Both stream to the agent over LiveKit data messages: the code as text,
and the whiteboard as a text summary (labelled shapes, arrows between them, notes). That summary
is cheaper and faster than screenshots, and it is what the interviewer reads when it calls
`view_candidate_workspace`.

Data messages:

| Topic | Direction | Payload |
|---|---|---|
| `question` | agent -> browser | active question for the problem panel |
| `code` | browser -> agent | editor contents + language |
| `whiteboard` | browser -> agent | whiteboard summary |
| `proctor` | browser -> agent | integrity event |
| `sync` | browser -> agent | ask the agent to resend the active question |

## Interview state machine (agent)

`services/agent/interviewer/state.py` holds the logic, with no LiveKit dependency:

- **Start:** a fixed greeting is spoken the moment the agent joins (no LLM wait) while the first
  question is pushed to the screen; then the LLM poses it.
- **Questions:** the LLM calls `next_question` when a question is explored enough. The tool
  updates the candidate's screen and returns the next prompt and its time budget.
- **Hints:** `get_hint` returns the next prepared hint for the active question and counts it.
  Hint counts and per-question notes go to the evaluator with the transcript.
- **Time:** phases `main -> wrap_up` (last 5 minutes or 20% of the round) `-> overtime`
  (2 minutes past). Phase changes update the interviewer's instructions; there is a hard stop
  soon after overtime.
- **Proctoring:** minor events are logged. Repeated ones (for example, two tab switches within
  2 minutes) trigger a spoken warning, at most once every 90s. Critical ones (screen share
  stopped, camera off, a second face) pause the interview until the browser reports `resumed`.
- **Latency:** one worker process stays warm (VAD loaded). Against a self-hosted LiveKit
  server the agent uses the local turn detector and VAD-based interruptions; LiveKit Cloud's
  hosted versions are used only when running on LiveKit Cloud.

## Proctoring (browser)

- **Lobby gate:** desktop browser, camera with exactly one face, microphone level check,
  `getDisplayMedia` with `displaySurface === "monitor"` (entire screen only), no extended display
  (`screen.isExtended`), consent.
- **Live:** track `ended`/`mute` events, `visibilitychange`, `blur`, `fullscreenchange`, screen
  `change`, and MediaPipe face checks every 1.5s (no face, multiple faces, head turned away). Pasting
  into the editor is blocked and logged.
- Events go to the agent over LiveKit data messages (so it can react) and to the API in batches
  (for the report).

Known limits: this can't detect a phone held out of camera view, and behaviour differs across
browsers (Chrome and Edge are the supported targets).
