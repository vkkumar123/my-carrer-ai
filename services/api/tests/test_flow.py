from app.config import get_settings
from app.llm.schemas import InterviewPlan
from tests.conftest import fake_round, login

INTERNAL = {"X-Internal-Key": "test-internal"}
RESUME_TEXT = ("Asha - Data Engineer. 3 years building Spark pipelines on AWS. " * 10).encode()


def upload_resume(client, auth) -> str:
    r = client.post(
        "/resumes", headers=auth, files={"file": ("resume.txt", RESUME_TEXT, "text/plain")}
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_requires_auth(client):
    assert client.get("/loops").status_code == 401


def test_company_loop_end_to_end(client, auth, fake_llm):
    resume_id = upload_resume(client, auth)
    r = client.post(
        "/loops",
        headers=auth,
        json={
            "mode": "company",
            "company": "adobe",
            "role": "Data Engineer",
            "level": "senior",
            "jd_text": "We need Spark and Kafka.",
            "resume_id": resume_id,
        },
    )
    assert r.status_code == 202, r.text
    loop_id = r.json()["id"]
    assert r.json()["title"] == "Adobe - Data Engineer"
    assert "Not affiliated" in r.json()["disclaimer"]

    loop = client.get(f"/loops/{loop_id}", headers=auth).json()
    assert loop["status"] == "ready"
    assert loop["gap_map"]["gaps"] == ["Kafka"]
    types = [x["type"] for x in loop["rounds"]]
    assert types == ["coding", "coding", "system_design", "hiring_manager"]  # senior: no LLD

    round_id = loop["rounds"][0]["id"]
    rnd = client.get(f"/rounds/{round_id}", headers=auth).json()
    assert rnd["plan"] is None  # questions hidden before the round

    join = client.post(f"/rounds/{round_id}/join", headers=auth)
    assert join.status_code == 200, join.text
    assert join.json()["token"] and join.json()["room"].startswith(f"round-{round_id}")

    # rejoin keeps the same room
    assert (
        client.post(f"/rounds/{round_id}/join", headers=auth).json()["room"] == join.json()["room"]
    )

    ev = client.post(
        f"/rounds/{round_id}/proctor-events",
        headers=auth,
        json={
            "events": [
                {"type": "tab_hidden", "severity": "warn"},
                {"type": "multiple_faces", "severity": "critical"},
            ]
        },
    )
    assert ev.status_code == 204

    ctx = client.get(f"/internal/rounds/{round_id}/context", headers=INTERNAL).json()
    assert ctx["company"] == "Adobe" and ctx["plan"]["questions"][0]["id"] == "q1"
    assert ctx["candidate"]["name"] == "Asha"

    transcript = [
        {"role": "interviewer", "text": "Hi"},
        {"role": "candidate", "text": "Hello"},
        {"role": "candidate", "text": "I built a Spark pipeline"},
        {"role": "candidate", "text": "It used partitioning"},
    ]
    done = client.post(
        f"/internal/rounds/{round_id}/complete",
        headers=INTERNAL,
        json={
            "transcript": transcript,
            "end_reason": "completed",
            "final_code": "SELECT 1",
            "final_whiteboard": "Box 'orders' -> Box 'customers'",
            "hints_used": {"q1": 1},
            "question_notes": {"q1": "Needed a hint on LEFT JOIN"},
        },
    )
    assert done.status_code == 202

    rnd = client.get(f"/rounds/{round_id}", headers=auth).json()
    assert rnd["status"] == "evaluated"
    assert rnd["evaluation"]["overall_score"] == 72
    assert rnd["integrity"]["score"] == 87 and rnd["integrity"]["rating"] == "clean"
    assert rnd["plan"] is not None and len(rnd["transcript"]) == 4
    assert rnd["final_whiteboard"].startswith("Box") and rnd["final_code"] == "SELECT 1"

    # finished rounds can't be rejoined; completion is idempotent
    assert client.post(f"/rounds/{round_id}/join", headers=auth).status_code == 409
    again = client.post(
        f"/internal/rounds/{round_id}/complete",
        headers=INTERNAL,
        json={"transcript": [], "end_reason": "x"},
    )
    assert again.json()["status"] == "evaluated"


def test_topic_loop_and_short_round(client, auth, fake_llm):
    r = client.post(
        "/loops", headers=auth, json={"mode": "topic", "topic": "Apache Spark", "duration_min": 20}
    )
    loop = client.get(f"/loops/{r.json()['id']}", headers=auth).json()
    assert loop["status"] == "ready"
    assert [(x["type"], x["duration_min"]) for x in loop["rounds"]] == [("topic", 20)]

    round_id = loop["rounds"][0]["id"]
    client.post(f"/rounds/{round_id}/join", headers=auth)
    client.post(
        f"/internal/rounds/{round_id}/complete",
        headers=INTERNAL,
        json={"transcript": [{"role": "candidate", "text": "hi"}], "end_reason": "left"},
    )
    rnd = client.get(f"/rounds/{round_id}", headers=auth).json()
    assert rnd["status"] == "insufficient" and rnd["evaluation"] is None


def test_unknown_company_uses_generic_template(client, auth, fake_llm):
    r = client.post(
        "/loops",
        headers=auth,
        json={"mode": "company", "company": "Zoho", "role": "SDE", "level": "junior"},
    )
    loop = client.get(f"/loops/{r.json()['id']}", headers=auth).json()
    assert loop["company"] == "Zoho"
    assert "low_level_design" in [x["type"] for x in loop["rounds"]]


def test_validation_and_isolation(client, auth, fake_llm):
    assert client.post("/loops", headers=auth, json={"mode": "topic"}).status_code == 422
    assert client.post("/loops", headers=auth, json={"mode": "company"}).status_code == 422

    r = client.post("/loops", headers=auth, json={"mode": "topic", "topic": "SQL"})
    loop_id = r.json()["id"]
    other = login(client, "ravi@example.com")
    assert client.get(f"/loops/{loop_id}", headers=other).status_code == 404
    round_id = client.get(f"/loops/{loop_id}", headers=auth).json()["rounds"][0]["id"]
    assert client.post(f"/rounds/{round_id}/join", headers=other).status_code == 404


def test_internal_requires_key(client):
    assert client.get("/internal/rounds/x/context").status_code == 403
    assert (
        client.get("/internal/rounds/x/context", headers={"X-Internal-Key": "no"}).status_code
        == 403
    )


def test_dev_login_disabled_outside_dev(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_mode", "supabase")
    assert client.post("/auth/dev-login", json={"email": "a@b.co"}).status_code == 404


def test_background_failures_land_in_final_state(client, auth, fake_llm, monkeypatch):
    from app.llm import tasks

    def boom(*a, **k):
        raise TypeError("no credentials")

    monkeypatch.setattr(tasks, "plan_loop", boom)
    r = client.post("/loops", headers=auth, json={"mode": "topic", "topic": "Kafka"})
    loop = client.get(f"/loops/{r.json()['id']}", headers=auth).json()
    assert loop["status"] == "failed" and loop["rounds"] == []

    monkeypatch.setattr(
        tasks,
        "plan_loop",
        lambda ctx, specs: InterviewPlan(
            rounds=[fake_round(x["type"], x["title"], x["duration_min"]) for x in specs]
        ),
    )
    retry = client.post(f"/loops/{loop['id']}/retry", headers=auth)
    assert retry.status_code == 202
    loop = client.get(f"/loops/{loop['id']}", headers=auth).json()
    assert loop["status"] == "ready" and len(loop["rounds"]) == 1

    round_id = loop["rounds"][0]["id"]
    client.post(f"/rounds/{round_id}/join", headers=auth)
    monkeypatch.setattr(tasks, "evaluate_round", boom)
    turns = [{"role": "candidate", "text": f"answer {i}"} for i in range(4)]
    client.post(
        f"/internal/rounds/{round_id}/complete",
        headers=INTERNAL,
        json={"transcript": turns, "end_reason": "completed"},
    )
    assert client.get(f"/rounds/{round_id}", headers=auth).json()["status"] == "eval_failed"


def test_agent_error_before_answers_gives_round_back(client, auth, fake_llm):
    r = client.post("/loops", headers=auth, json={"mode": "topic", "topic": "Go"})
    round_id = client.get(f"/loops/{r.json()['id']}", headers=auth).json()["rounds"][0]["id"]
    first_room = client.post(f"/rounds/{round_id}/join", headers=auth).json()["room"]
    res = client.post(
        f"/internal/rounds/{round_id}/complete",
        headers=INTERNAL,
        json={"transcript": [{"role": "interviewer", "text": "Hi"}], "end_reason": "agent_error"},
    )
    assert res.json()["status"] == "pending"
    rejoin = client.post(f"/rounds/{round_id}/join", headers=auth)
    assert rejoin.status_code == 200 and rejoin.json()["room"] != first_room
