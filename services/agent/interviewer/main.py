"""LiveKit voice agent that runs one interview round.

Pipeline: candidate mic -> Silero VAD + turn detector -> Deepgram STT -> Claude (fast model)
-> Deepgram TTS -> candidate speakers.

Data messages (LiveKit, JSON):
- browser -> agent: "proctor" (integrity events), "code" and "whiteboard" (live workspace),
  "sync" (browser (re)joined, resend the current question)
- agent -> browser: "question" (problem panel content for the active question)
"""

import asyncio
import json
import logging
import os
import time
import urllib.request
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    CloseEvent,
    ConversationItemAddedEvent,
    EndpointingOptions,
    InterruptionOptions,
    JobContext,
    JobProcess,
    RunContext,
    StopResponse,
    TurnHandlingOptions,
    UserStateChangedEvent,
    cli,
    function_tool,
    inference,
    llm,
)
from livekit.agents.voice.room_io import RoomOptions
from livekit.plugins import anthropic, deepgram, silero

from interviewer import api_client
from interviewer.prompts import build_instructions, greeting, phase_note
from interviewer.state import InterviewState, Phase, ProctorMonitor

load_dotenv()
log = logging.getLogger("interviewer")

LLM_MODEL = os.environ.get("LLM_MODEL_FAST", "claude-haiku-4-5")
STT_MODEL = os.environ.get("DEEPGRAM_STT_MODEL", "nova-3")
STT_LANGUAGE = os.environ.get("DEEPGRAM_STT_LANGUAGE", "en")
TTS_MODEL = os.environ.get("DEEPGRAM_TTS_MODEL", "aura-2-andromeda-en")
INTERVIEWER_NAME = os.environ.get("INTERVIEWER_NAME", "Alex")
HARD_STOP_GRACE_S = 90
QUIET_WORK_TYPES = {"coding", "low_level_design", "system_design"}

# LiveKit's cloud inference (turn detector, adaptive interruptions) only works against
# LiveKit Cloud. Against a self-hosted/local server it fails and retries before falling
# back, which delays the start of the interview, so use the local equivalents there.
ON_LIVEKIT_CLOUD = (urlparse(os.environ.get("LIVEKIT_URL", "")).hostname or "").endswith(
    ".livekit.cloud"
)

# Words STT often mishears in tech interviews (e.g. "CTE" -> "city").
BASE_KEYTERMS = [
    "SQL",
    "CTE",
    "COALESCE",
    "GROUP BY",
    "LEFT JOIN",
    "INNER JOIN",
    "PARTITION BY",
    "ROW_NUMBER",
    "DENSE_RANK",
    "LAG",
    "LEAD",
    "HashMap",
    "API",
    "Kafka",
    "Spark",
    "Redis",
    "PostgreSQL",
    "Kubernetes",
    "Big O",
]


class Interviewer(Agent):
    def __init__(self, ctx_data: dict[str, Any], state: InterviewState, job: JobContext) -> None:
        self._base_instructions = build_instructions(ctx_data, INTERVIEWER_NAME)
        super().__init__(instructions=self._base_instructions)
        self.ctx_data = ctx_data
        self.state = state
        self.proctor = ProctorMonitor()
        self._job = job

    async def on_enter(self) -> None:
        # Speak a fixed greeting straight away instead of waiting for the LLM, then show the
        # first question and let the LLM pose it.
        self.session.say(greeting(self.ctx_data, INTERVIEWER_NAME), allow_interruptions=False)
        await publish_question(self._job.room, self.state)
        self.session.generate_reply(
            instructions="Now ask the first planned question using its prompt. Keep it short; "
            "the details are on the candidate's screen."
        )

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        # While paused for a proctoring issue, don't carry on the interview.
        if self.proctor.paused_for is not None:
            raise StopResponse()

    def apply_phase(self, phase: Phase) -> None:
        note = phase_note(phase.value, self.state.remaining_min())
        text = self._base_instructions + (f"\n# Timing\n{note}\n" if note else "")
        asyncio.create_task(self.update_instructions(text))

    @function_tool
    async def next_question(self, context: RunContext, summary: str) -> str:
        """Close the current planned question, show the next one on the candidate's screen,
        and get what to ask next.

        Args:
            summary: One short sentence on how the candidate handled the question just finished.
        """
        result = self.state.advance(summary)
        await publish_question(self._job.room, self.state)
        return result

    @function_tool
    async def view_candidate_workspace(self, context: RunContext) -> str:
        """See what the candidate has written in the code editor and drawn on the whiteboard."""
        return self.state.workspace_view()

    @function_tool
    async def get_hint(self, context: RunContext) -> str:
        """Get the next prepared hint for the current question. Use only when the candidate
        asks for help or is clearly stuck."""
        return self.state.next_hint()

    @function_tool
    async def end_interview(self, context: RunContext, reason: str) -> None:
        """End the interview. Call only after you have said goodbye to the candidate.

        Args:
            reason: Why it ended, e.g. "completed", "candidate_requested", "time_up".
        """
        self.state.ended = True
        self.state.end_reason = reason
        await context.wait_for_playout()
        self._job.shutdown(reason=f"interview ended: {reason}")


async def publish_question(room: rtc.Room, state: InterviewState) -> None:
    payload = state.question_payload()
    if payload is None:
        return
    try:
        await room.local_participant.publish_data(
            json.dumps(payload), reliable=True, topic="question"
        )
    except Exception:
        log.exception("could not publish question to the candidate's screen")


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


def _worker_proxy() -> str | None:
    """HTTPS proxy for the worker's LiveKit connection, honouring NO_PROXY.

    LiveKit Agents reads HTTPS_PROXY but ignores NO_PROXY, which breaks a local LiveKit
    server behind a corporate/sandbox proxy.
    """
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    host = urlparse(os.environ.get("LIVEKIT_URL", "")).hostname or ""
    if proxy and host and urllib.request.proxy_bypass_environment(host):
        return None
    return proxy


# Keep one process warm (VAD loaded) so a new interview starts without spawn/load delay.
server = AgentServer(setup_fnc=prewarm, http_proxy=_worker_proxy(), num_idle_processes=1)


def _turn_handling() -> TurnHandlingOptions:
    # Candidates pause to think mid-answer; don't jump in too early.
    endpointing = EndpointingOptions(min_delay=0.8, max_delay=6.0)
    if ON_LIVEKIT_CLOUD:
        return TurnHandlingOptions(turn_detection=inference.TurnDetector(), endpointing=endpointing)
    return TurnHandlingOptions(
        turn_detection=inference.TurnDetector(version="v1-mini"),
        endpointing=endpointing,
        interruption=InterruptionOptions(mode="vad"),
    )


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    metadata = json.loads(ctx.job.metadata or "{}")
    round_id = metadata.get("round_id")
    if not round_id:
        log.error("job without round_id metadata; leaving")
        return
    ctx.log_context_fields = {"round_id": round_id}

    ctx_data = await api_client.fetch_round_context(round_id)
    if ctx_data["status"] != "in_progress":
        log.warning("round %s is %s; not starting", round_id, ctx_data["status"])
        return

    state = InterviewState(
        questions=ctx_data["plan"]["questions"], duration_min=ctx_data["duration_min"]
    )
    transcript: list[dict[str, Any]] = []
    keyterms = _keyterms(ctx_data)

    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(
            model=STT_MODEL,
            language=STT_LANGUAGE,
            smart_format=True,
            **({"keyterm": keyterms} if keyterms and STT_MODEL.startswith("nova-3") else {}),
        ),
        llm=anthropic.LLM(model=LLM_MODEL, caching="ephemeral", max_tokens=400),
        tts=deepgram.TTS(model=TTS_MODEL),
        turn_handling=_turn_handling(),
        # Silence is normal while writing code or drawing; check in later there.
        user_away_timeout=60.0 if ctx_data["type"] in QUIET_WORK_TYPES else 30.0,
        max_tool_steps=4,
    )
    agent = Interviewer(ctx_data, state, ctx)

    @session.on("conversation_item_added")
    def _on_item(ev: ConversationItemAddedEvent) -> None:
        item = ev.item
        if not isinstance(item, llm.ChatMessage) or item.role not in ("user", "assistant"):
            return
        text = (item.text_content or "").strip()
        if text:
            role = "candidate" if item.role == "user" else "interviewer"
            transcript.append({"role": role, "text": text, "at": ev.created_at})

    @session.on("user_state_changed")
    def _on_user_state(ev: UserStateChangedEvent) -> None:
        if ev.new_state == "away" and not state.ended and agent.proctor.paused_for is None:
            session.generate_reply(
                instructions="The candidate has been quiet for a while. Check in briefly: if "
                "they're working in the editor or whiteboard, call view_candidate_workspace "
                "first and ask how it's going; otherwise tell them to take their time or "
                "offer to rephrase."
            )

    def _on_data(packet: rtc.DataPacket) -> None:
        try:
            data = json.loads(packet.data.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if packet.topic == "code":
            state.latest_code = str(data.get("code", ""))[:50_000]
            state.code_language = data.get("language")
        elif packet.topic == "whiteboard":
            state.latest_whiteboard = str(data.get("summary", ""))[:20_000]
        elif packet.topic == "sync":
            asyncio.create_task(publish_question(ctx.room, state))
        elif packet.topic == "proctor" and not state.ended:
            line = agent.proctor.handle(str(data.get("type", "")))
            if line:
                session.interrupt()
                session.say(line, allow_interruptions=False)

    ctx.room.on("data_received", _on_data)

    @session.on("close")
    def _on_close(ev: CloseEvent) -> None:
        # Candidate left, the interviewer ended it, or a provider failed: finish the job now
        # rather than waiting for LiveKit to tear down the empty room.
        if ev.error is not None:
            log.error("session closed with error: %s", ev.error)
            state.end_reason = state.end_reason or "agent_error"
        ctx.shutdown(reason=f"session closed: {ev.reason}")

    async def _clock() -> None:
        last = Phase.MAIN
        while not state.ended:
            await asyncio.sleep(10)
            phase = state.phase()
            if phase != last:
                last = phase
                agent.apply_phase(phase)
                if phase == Phase.OVERTIME:
                    session.generate_reply(instructions=phase_note("overtime", 0))
            if state.remaining_min() * 60 < -(HARD_STOP_GRACE_S + 120):
                log.info("hard stop: round over time")
                state.end_reason = "time_up"
                ctx.shutdown(reason="time up")
                return

    async def _on_shutdown(reason: str) -> None:
        end_reason = state.end_reason or ("candidate_left" if not state.ended else "completed")
        log.info("round %s ending (%s); %d transcript turns", round_id, reason, len(transcript))
        await api_client.complete_round(
            round_id,
            transcript=transcript,
            final_code=state.latest_code,
            final_whiteboard=state.latest_whiteboard,
            hints_used=state.hints_used,
            question_notes=state.notes,
            end_reason=end_reason,
        )

    ctx.add_shutdown_callback(_on_shutdown)

    started = time.monotonic()
    # Connect before starting the session so on_enter can publish the first question.
    await ctx.connect()
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=RoomOptions(video_input=False, close_on_disconnect=True),
    )
    log.info("session started in %.1fs", time.monotonic() - started)
    state.started_at = time.monotonic()
    clock = asyncio.create_task(_clock())
    ctx.add_shutdown_callback(lambda: _cancel(clock))


async def _cancel(task: asyncio.Task) -> None:
    task.cancel()


def _keyterms(ctx_data: dict[str, Any]) -> list[str]:
    """Technical words that help STT spell things like 'Kafka' or 'HashMap' correctly."""
    terms: list[str] = [q["topic"] for q in ctx_data["plan"]["questions"]]
    for extra in (ctx_data.get("topic"), ctx_data.get("company")):
        if extra:
            terms.append(extra)
    terms += (ctx_data.get("candidate") or {}).get("skills", [])
    terms += BASE_KEYTERMS
    seen: dict[str, None] = {}
    for t in terms:
        t = t.strip()
        if t and len(t) <= 40:
            seen.setdefault(t, None)
    return list(seen)[:80]


if __name__ == "__main__":
    cli.run_app(server)
