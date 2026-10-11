import re
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app import create_app
from models import AssessmentAnswer, AssessmentAttempt, RoadmapProgress
from roadmaps import ROADMAPS, progress_summary, roadmap_for


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret-key", "DATABASE_URL": f"sqlite:///{tmp_path / 'test.sqlite3'}"})
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_token(client, path):
    response = client.get(path)
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match
    return match.group(1)


def register(client, name="Ada Lovelace", email="ada@example.com"):
    client.post("/register", data={"csrf_token": csrf_token(client, "/register"), "name": name, "email": email, "password": "correct-horse-battery-staple", "password_confirmation": "correct-horse-battery-staple"})


def account_id(client):
    with client.session_transaction() as session:
        return session["user_id"]


def add_completed_attempt(app, user_id):
    with app.app_context():
        session = app.extensions["db_session"]
        attempt = AssessmentAttempt(user_id=user_id, status="completed", programming_score=100, logical_reasoning_score=75, problem_solving_score=75, analytical_thinking_score=50, overall_score=75, completed_at=datetime.now(timezone.utc))
        session.add(attempt)
        session.flush()
        for question_id, value in {"interest_activity": "a", "interest_problem": "a", "interest_learning": "a"}.items():
            session.add(AssessmentAnswer(attempt_id=attempt.id, question_id=question_id, answer_value=value))
        session.commit()


def test_roadmap_catalog_has_ordered_complete_content():
    assert set(ROADMAPS) == {"software-developer", "data-analyst", "cybersecurity-analyst", "game-developer", "ui-ux-designer", "qa-test-engineer"}
    roadmap = roadmap_for("software-developer")
    assert [stage["name"] for stage in roadmap["stages"]] == ["Beginner", "Intermediate", "Advanced"]
    assert [item["id"] for item in roadmap["stages"][0]["milestones"]] == ["sd-python-basics", "sd-version-control"]
    for path in ROADMAPS.values():
        for stage in path["stages"]:
            for item in stage["milestones"]:
                assert item["topic"] and item["description"] and item["criterion"] and item["resources"]
                assert all(resource["title"] and resource["url"].startswith("https://") for resource in item["resources"])


def test_progress_summary_uses_only_completed_milestones():
    roadmap = roadmap_for("software-developer")
    empty = progress_summary(roadmap, {})
    assert empty["percentage"] == 0
    assert [stage["percentage"] for stage in empty["stages"]] == [0, 0, 0]
    partial = progress_summary(roadmap, {"sd-python-basics": "completed", "sd-version-control": "in_progress"})
    assert (partial["completed"], partial["total"], partial["percentage"], partial["stages"][0]["percentage"]) == (1, 6, 17, 50)


def test_roadmap_routes_require_assessment_and_validate_career(client, app):
    assert client.get("/roadmaps", follow_redirects=False).status_code == 302
    register(client)
    assert b"Complete an assessment first." in client.get("/roadmaps").data
    add_completed_attempt(app, account_id(client))
    assert b"Software Developer" in client.get("/roadmaps").data
    assert client.get("/roadmaps/software-developer").status_code == 200
    assert client.get("/roadmaps/not-a-career").status_code == 404


def test_progress_saves_updates_and_persists_across_requests(client, app):
    register(client)
    add_completed_attempt(app, account_id(client))
    path = "/roadmaps/software-developer"
    update_path = "/roadmaps/software-developer/milestones/sd-python-basics/progress"
    response = client.post(update_path, data={"csrf_token": csrf_token(client, path), "status": "completed"}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/roadmaps/software-developer#stage-beginner")
    page = client.get(path)
    assert b"17%" in page.data
    assert b"1 of 6 milestones completed" in page.data
    response = client.post(update_path, data={"csrf_token": csrf_token(client, path), "status": "in_progress"})
    assert response.status_code == 302
    with app.app_context():
        rows = app.extensions["db_session"].scalars(select(RoadmapProgress)).all()
        assert len(rows) == 1
        assert rows[0].status == "in_progress"
    assert b"0 of 6 milestones completed" in client.get(path).data
    response = client.post(update_path, data={"csrf_token": csrf_token(client, path), "status": "not_started"})
    assert response.status_code == 302
    with app.app_context():
        assert app.extensions["db_session"].scalar(select(RoadmapProgress)).status == "not_started"


def test_progress_rejects_invalid_status_milestone_and_csrf(client, app):
    register(client)
    add_completed_attempt(app, account_id(client))
    path = "/roadmaps/software-developer"
    update_path = "/roadmaps/software-developer/milestones/sd-python-basics/progress"
    assert client.post(update_path, data={"csrf_token": "invalid", "status": "completed"}).status_code == 400
    assert client.post(update_path, data={"csrf_token": csrf_token(client, path), "status": "done"}).status_code == 400
    assert client.post("/roadmaps/software-developer/milestones/nope/progress", data={"csrf_token": csrf_token(client, path), "status": "completed"}).status_code == 404


def test_progress_is_scoped_to_each_authenticated_user(client, app):
    register(client)
    first_user_id = account_id(client)
    add_completed_attempt(app, first_user_id)
    path = "/roadmaps/software-developer"
    update_path = "/roadmaps/software-developer/milestones/sd-python-basics/progress"
    client.post(update_path, data={"csrf_token": csrf_token(client, path), "status": "completed"})
    other_client = app.test_client()
    register(other_client, name="Grace Hopper", email="grace@example.com")
    second_user_id = account_id(other_client)
    add_completed_attempt(app, second_user_id)
    assert b"0 of 6 milestones completed" in other_client.get(path).data
    other_client.post(update_path, data={"csrf_token": csrf_token(other_client, path), "status": "in_progress"})
    with app.app_context():
        rows = app.extensions["db_session"].scalars(select(RoadmapProgress).order_by(RoadmapProgress.user_id)).all()
        assert len(rows) == 2
        assert [(row.user_id, row.status) for row in rows] == [(first_user_id, "completed"), (second_user_id, "in_progress")]
