from interviewer.prompts import build_instructions, greeting, phase_note
from interviewer.state import InterviewState, Phase, ProctorMonitor

QUESTIONS = [
    {
        "id": "q1",
        "prompt": "Write the query.",
        "topic": "SQL joins",
        "difficulty": "easy",
        "screen_text": "orders(order_id, customer_id, amount)",
        "workspace": "code",
        "language": "sql",
        "follow_ups": ["Why?"],
        "hints": ["Think LEFT JOIN", "Use COALESCE"],
        "what_good_looks_like": "LEFT JOIN",
    },
    # Older plans have no screen/workspace/hint fields; they must still work.
    {
        "id": "q2",
        "prompt": "Design a pipeline.",
        "topic": "Design",
        "difficulty": "hard",
        "follow_ups": [],
        "what_good_looks_like": "Idempotency",
    },
]


def make_state(duration: int = 30) -> InterviewState:
    return InterviewState(questions=QUESTIONS, duration_min=duration, started_at=0.0)


def test_phases_follow_the_clock():
    s = make_state(30)
    assert s.phase(now=10 * 60) == Phase.MAIN
    assert s.phase(now=26 * 60) == Phase.WRAP_UP
    assert s.phase(now=33 * 60) == Phase.OVERTIME


def test_short_round_wraps_up_proportionally():
    s = make_state(15)
    assert s.phase(now=11 * 60) == Phase.MAIN  # 4 min left > 20% of 15
    assert s.phase(now=12.5 * 60) == Phase.WRAP_UP


def test_advance_walks_questions_then_wraps(monkeypatch):
    s = make_state(30)
    monkeypatch.setattr(s, "remaining_min", lambda now=None: 20.0)
    monkeypatch.setattr(s, "phase", lambda now=None: Phase.MAIN)
    msg = s.advance("ok")
    assert "q2" in msg and "Design a pipeline." in msg
    assert s.completed == ["q1"]
    msg = s.advance("ok")
    assert "wrapping up" in msg
    assert s.current_question is None


def test_proctor_warns_only_on_repeats_and_respects_cooldown():
    m = ProctorMonitor()
    assert m.handle("tab_hidden", now=0) is None
    assert "switched away" in m.handle("tab_hidden", now=10)
    assert m.handle("tab_hidden", now=20) is None
    assert m.handle("tab_hidden", now=30) is None  # cooldown
    assert m.handle("unknown_event", now=40) is None


def test_proctor_pauses_on_critical_until_resumed():
    m = ProctorMonitor()
    assert "screen" in m.handle("screen_share_stopped", now=0)
    assert m.paused_for == "screen_share_stopped"
    assert m.handle("screen_share_stopped", now=5) is None  # no repeats
    assert "continue" in m.handle("resumed", now=30)
    assert m.paused_for is None
    assert m.handle("resumed", now=31) is None


def test_instructions_include_plan_and_hide_nothing_needed():
    ctx = {
        "mode": "company",
        "round_index": 0,
        "total_rounds": 4,
        "title": "Coding Round 1",
        "level": "mid",
        "role": "SDE",
        "company": "Adobe",
        "duration_min": 45,
        "type": "coding",
        "persona": {"style": "Friendly", "pace": "moderate"},
        "plan": {"objective": "DSA", "questions": QUESTIONS},
        "candidate": {"name": "Asha"},
        "candidate_name": "Asha",
    }
    text = build_instructions(ctx, "Alex")
    assert "Adobe" in text and "Asha" in text and "orders(order_id" in text
    assert "next_question" in text and "view_candidate_workspace" in text
    assert "get_hint" in text and "Coding Round 1" in text
    assert phase_note("main", 10) is None
    assert "5 minutes" in phase_note("wrap_up", 5)


def test_hints_are_progressive_and_counted():
    s = make_state()
    assert "Think LEFT JOIN" in s.next_hint()
    assert "Use COALESCE" in s.next_hint()
    assert "No more prepared hints" in s.next_hint()
    assert s.hints_used == {"q1": 2}
    s.current = 1
    assert "No more prepared hints" in s.next_hint()  # question without hints


def test_question_payload_and_workspace_view():
    s = make_state()
    p = s.question_payload()
    assert p["screen_text"].startswith("orders(") and p["workspace"] == "code"
    assert p["language"] == "sql" and p["index"] == 0 and p["total"] == 2
    assert "EDITOR: empty." in s.workspace_view() and "WHITEBOARD: empty." in s.workspace_view()
    s.latest_code, s.code_language = "SELECT 1", "sql"
    s.latest_whiteboard = "Box 'API' -> Box 'DB'"
    view = s.workspace_view()
    assert "EDITOR (sql):\nSELECT 1" in view and "Box 'API'" in view
    s.current = 1
    assert s.question_payload()["workspace"] == "none"  # old plan defaults
    s.current = 2
    assert s.question_payload() is None


def test_advance_records_note():
    s = make_state()
    s.advance("Needed a hint")
    assert s.notes == {"q1": "Needed a hint"}


def test_greeting_uses_first_name_and_mentions_tools():
    ctx = {
        "mode": "topic",
        "topic": "SQL",
        "duration_min": 15,
        "candidate": None,
        "candidate_name": "Vivek Kumar",
    }
    g = greeting(ctx, "Alex")
    assert g.startswith("Hi Vivek, I'm Alex") and "15 minutes" in g and "whiteboard" in g
