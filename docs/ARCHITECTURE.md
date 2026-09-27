# Architecture notes

## Data model

- `users`: created from the Supabase JWT on first request (or `/auth/dev-login` locally).
- `resumes`: original file in storage, extracted text, and a parsed profile (JSON).
- `interview_loops`: one practice session. `mode` is `topic` or `company`; `spec` holds the
  blueprint output (persona, round list, disclaimer); `jd_parsed` and `gap_map` come from the LLM.
- `rounds`: one per interview round. `plan` (questions + rubric) stays hidden from the candidate
  until the round ends. Holds the transcript, final code, evaluation and integrity summary.
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

## Interview state machine (agent)

`services/agent/interviewer/state.py` holds the logic, with no LiveKit dependency:

- **Questions:** the LLM calls `next_question` when a question is explored enough. The tool returns
  the next planned question and how many minutes it has.
- **Time:** phases `main -> wrap_up` (last 5 minutes or 20% of the round) `-> overtime`
  (2 minutes past). Phase changes update the interviewer's instructions; there is a hard stop soon
  after overtime.
- **Proctoring:** minor events are logged. Repeated ones (for example, two tab switches within
  2 minutes) trigger a spoken warning, at most once every 90s. Critical ones (screen share stopped,
  camera off, a second face) pause the interview until the browser reports `resumed`.

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
