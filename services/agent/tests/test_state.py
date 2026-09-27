from interviewer.prompts import build_instructions, phase_note
from interviewer.state import InterviewState, Phase, ProctorMonitor

QUESTIONS = [
    {
        "id": "q1",
        "prompt": "Explain Spark partitions.",
        "topic": "Spark",
        "difficulty": "easy",
        "follow_ups": ["Why?"],
        "what_good_looks_like": "Mentions shuffles",
    },
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
    assert "Adobe" in text and "Asha" in text and "Explain Spark partitions." in text
    assert "next_question" in text and "get_candidate_code" in text
    assert phase_note("main", 10) is None
    assert "5 minutes" in phase_note("wrap_up", 5)
