import os
import tempfile

_db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file}"
os.environ["AUTH_MODE"] = "dev"
os.environ["INTERNAL_API_KEY"] = "test-internal"
os.environ["LIVEKIT_API_SECRET"] = "test-livekit-secret-that-is-long-enough-0123"
os.environ["STORAGE_LOCAL_DIR"] = tempfile.mkdtemp()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.llm import schemas as s  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def login(client: TestClient, email: str = "asha@example.com") -> dict[str, str]:
    r = client.post("/auth/dev-login", json={"email": email, "name": "Asha"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client) -> dict[str, str]:
    return login(client)


def fake_round(rtype: str, title: str, minutes: int) -> s.RoundPlan:
    return s.RoundPlan(
        type=rtype,
        title=title,
        duration_min=minutes,
        objective="Assess problem solving",
        questions=[
            s.PlannedQuestion(
                id="q1",
                prompt="Write a query listing each customer's total order amount.",
                topic="SQL joins",
                difficulty="easy",
                screen_text="orders(order_id INT, customer_id INT, amount DECIMAL)",
                workspace="code",
                language="sql",
                setup_sql="CREATE TABLE orders(order_id INTEGER, customer_id INTEGER, "
                "amount DECIMAL(10,2)); INSERT INTO orders VALUES (1, 1, 10.5);",
                follow_ups=["What changes with a LEFT JOIN?"],
                hints=["Which join keeps customers without orders?"],
                what_good_looks_like="LEFT JOIN + COALESCE(SUM(amount), 0)",
            )
        ],
        rubric=[s.RubricItem(dimension="Problem solving", weight=3, description="Optimal")],
    )


RESEARCH = {
    "rounds": [
        {"type": "coding", "title": "DSA", "duration_min": 30, "focus": "arrays"},
        {"type": "system_design", "title": "HLD", "duration_min": 75, "focus": "scale"},
        {"type": "hiring_manager", "title": "HM", "duration_min": 45, "focus": "projects"},
    ],
    "interviewer_style": "Friendly but fast",
    "common_topics": ["DP", "graphs"],
    "question_patterns": ["Design a URL shortener"],
    "difficulty_notes": "Medium",
    "confidence": "medium",
}


@pytest.fixture
def fake_llm(monkeypatch):
    from app.llm import research, tasks

    calls = {"research": 0}

    def fake_research(company, role):
        calls["research"] += 1
        return RESEARCH, [{"url": "https://example.com/zoho", "title": "Zoho experience"}]

    monkeypatch.setattr(research, "_research", fake_research)

    def plan_loop(context, round_specs):
        return s.InterviewPlan(
            rounds=[fake_round(r["type"], r["title"], r["duration_min"]) for r in round_specs]
        )

    monkeypatch.setattr(tasks, "plan_loop", plan_loop)
    monkeypatch.setattr(
        tasks,
        "parse_resume",
        lambda text: s.ResumeProfile(
            name="Asha",
            headline="Data Engineer",
            years_experience=3,
            skills=["Spark"],
            experiences=[],
            projects=[],
            education=[],
        ),
    )
    monkeypatch.setattr(
        tasks,
        "parse_jd",
        lambda jd, company, role: s.JDProfile(
            title=role,
            company=company,
            seniority="mid",
            must_have=["Spark", "Kafka"],
            nice_to_have=[],
            responsibilities=[],
        ),
    )
    monkeypatch.setattr(
        tasks,
        "build_gap_map",
        lambda resume, jd: s.GapMap(strengths=["Spark"], gaps=["Kafka"], probe_areas=[]),
    )
    monkeypatch.setattr(
        tasks,
        "evaluate_round",
        lambda plan, transcript, code, ctx: s.Evaluation(
            overall_score=72,
            verdict="hire",
            summary="Solid",
            dimension_scores=[],
            question_feedback=[],
            strengths=["Clear"],
            improvements=[],
            study_plan=[],
            communication_notes="Good pace",
        ),
    )
    return calls
