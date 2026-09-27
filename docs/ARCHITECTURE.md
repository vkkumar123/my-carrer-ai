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
| Research the company's interview style (web search, cached 30 days per company + role family) | API background job | smart + web search |
| Plan rounds (questions, follow-ups, rubric, SQL sample tables) | API background job | smart, high effort |
| Live interviewer turns | Agent, per candidate turn | fast |
| Evaluate round | API background job after the round | smart, high effort |

The API uses structured outputs (Pydantic schemas in `services/api/app/llm/schemas.py`), so every
response is validated. Models are set by `LLM_MODEL_SMART` / `LLM_MODEL_FAST`.

## Questions and the candidate's workspace

Each planned question has:

- `prompt`: what the interviewer says (1-2 sentences, one ask)
- `screen_text`: what the problem panel shows (schemas, sample data, requirements)
- `workspace`: `code`, `whiteboard` or `none`, plus a `language` for code
- `setup_sql`: for SQL questions, DuckDB statements that create and fill the sample tables.
  The API runs them through DuckDB at planning time and asks the model to fix them if they
  fail, so the candidate's Run button always has working tables.
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
| `run` | browser -> agent | output or error of the candidate's last Run |
| `proctor` | browser -> agent | integrity event |
| `sync` | browser -> agent | ask the agent to resend the active question |

## Interview state machine (agent)

`services/agent/interviewer/state.py` holds the logic, with no LiveKit dependency:

- **Start:** a fixed greeting is spoken the moment the agent joins (no LLM wait) while the first
  question is pushed to the screen; then the LLM poses it.
- **Questions:** the LLM calls `next_question` when a question is explored enough. The tool
  updates the candidate's screen and returns the next prompt and its time budget.
- **Coding:** approach first (explain the idea and complexity), then write, run and discuss.
- **Hints:** `get_hint` returns the next prepared hint for the active question and counts it.
  Hint counts and per-question notes go to the evaluator with the transcript.
- **Time:** phases `main -> wrap_up` (last 5 minutes or 20% of the round) `-> overtime`
  (2 minutes past). Phase changes update the interviewer's instructions; there is a hard stop
  soon after overtime.
- **Early end:** the interviewer may wrap up when the candidate can't progress, but the tool
  refuses before 25 minutes (or half the round, for short rounds).
- **Proctoring:** minor events are logged. Repeated ones (for example, two tab switches within
  2 minutes) trigger a spoken warning, at most once every 90s. Critical ones (screen share
  stopped, camera off, a second face) pause the interview until the browser reports `resumed`.
  Warnings are strikes: strike 1 warns, strike 2 is a final warning that says the next one
  ends the interview, strike 3 ends it with the reason stated (`end_reason = integrity`).
  A second person on camera is a strike immediately; a lost screen share or camera counts
  from the second time.
- **Language and voice:** Sarvam speech-to-text auto-detects the language (code-mixed
  Hinglish mode). When the candidate speaks Hindi, the interviewer replies in Hindi and the
  voice switches to Hindi; otherwise English (Indian accent). Female voice "Priya" or male
  "Rahul", chosen in the lobby.
- **Latency:** one worker process stays warm (VAD loaded). Against a self-hosted LiveKit
  server the agent uses the local turn detector and VAD-based interruptions; LiveKit Cloud's
  hosted versions are used only when running on LiveKit Cloud.

## Running code (browser)

- **SQL:** DuckDB-wasm. Each run gets a fresh schema, loads the question's sample tables,
  then runs the candidate's SQL (multiple statements allowed). Results show as a table;
  dates and decimals are formatted from the column types.
- **Python:** Pyodide in a module Web Worker. Loads in the background when Python is
  selected; each run has a fresh namespace and a 10s limit (the worker is replaced after an
  infinite loop).
- Other languages can be written and discussed but not run yet.
- The editor, SQL and Python runtimes and the face detector are served from the app's own
  `/vendor` folder (copied from node_modules at build time by `scripts/copy-vendor.mjs`), so
  the product doesn't depend on a public CDN that office or college networks may block.
  `NEXT_PUBLIC_VENDOR_BASE_URL` can point them at object storage instead.

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
