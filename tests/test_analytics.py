import re
from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from models import AssessmentAttempt, RoadmapProgress


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'test.sqlite3'}",
    })
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_token(client, path):
    response = client.get(path)
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match, "CSRF token was not rendered"
    return match.group(1)


def register(client, name="Ada Lovelace", email="ada@example.com"):
    response = client.post("/register", data={
        "csrf_token": csrf_token(client, "/register"),
        "name": name,
        "email": email,
        "password": "correct-horse-battery-staple",
        "password_confirmation": "correct-horse-battery-staple",
    })
    assert response.status_code == 302


def account_id(client):
    with client.session_transaction() as browser_session:
        return browser_session["user_id"]


def add_completed_attempt(app, user_id, *, overall_score=75, scores=None, completed_at=None):
    scores = scores or {
        "programming": 100,
        "logical_reasoning": 75,
        "problem_solving": 75,
        "analytical_thinking": 51,
    }
    with app.app_context():
        db_session = app.extensions["db_session"]
        attempt = AssessmentAttempt(
            user_id=user_id,
            status="completed",
            programming_score=scores.get("programming"),
            logical_reasoning_score=scores.get("logical_reasoning"),
            problem_solving_score=scores.get("problem_solving"),
            analytical_thinking_score=scores.get("analytical_thinking"),
            overall_score=overall_score,
            completed_at=completed_at or datetime.now(timezone.utc),
        )
        db_session.add(attempt)
        db_session.commit()
        return attempt.id


def test_analytics_requires_login_and_has_honest_empty_states(client):
    response = client.get("/analytics", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    register(client)
    page = client.get("/analytics")
    assert page.status_code == 200
    assert b"No completed assessment yet" in page.data
    assert b"No roadmap progress yet" in page.data
    assert b">Progress Analytics<" in page.data


def test_analytics_uses_ten_newest_valid_attempts_and_compares_previous(client, app):
    register(client)
    user_id = account_id(client)
    now = datetime.now(timezone.utc)

    # This newest completed record is malformed and must not displace valid data.
    add_completed_attempt(
        app,
        user_id,
        overall_score=110,
        completed_at=now + timedelta(minutes=1),
    )
    for score in range(50, 61):
        add_completed_attempt(
            app,
            user_id,
            overall_score=score,
            completed_at=now - timedelta(days=60 - score),
        )

    content = client.get("/analytics").get_data(as_text=True)
    assert "Latest overall score" in content
    assert ">60%<" in content
    assert "+1 points" in content
    assert "Programming fundamentals" in content
    assert "110%" not in content
    assert content.count("<tbody>") == 1
    assert content.count("<tr>") == 11  # One header plus the ten newest valid records.
    assert ">50%<" not in content


def test_analytics_keeps_assessments_and_roadmap_progress_private(client, app):
    register(client)
    first_user_id = account_id(client)
    add_completed_attempt(app, first_user_id, overall_score=88)
    with app.app_context():
        db_session = app.extensions["db_session"]
        db_session.add(RoadmapProgress(
            user_id=first_user_id,
            career_id="software-developer",
            milestone_id="sd-python-basics",
            status="completed",
        ))
        db_session.commit()

    other_client = app.test_client()
    register(other_client, name="Grace Hopper", email="grace@example.com")
    content = other_client.get("/analytics").get_data(as_text=True)
    assert "88%" not in content
    assert "Software Developer" not in content
    assert "No completed assessment yet" in content
    assert "No roadmap progress yet" in content


def test_analytics_shows_actual_valid_roadmap_completion(client, app):
    register(client)
    user_id = account_id(client)
    with app.app_context():
        db_session = app.extensions["db_session"]
        db_session.add_all([
            RoadmapProgress(
                user_id=user_id,
                career_id="software-developer",
                milestone_id="sd-python-basics",
                status="completed",
            ),
            RoadmapProgress(
                user_id=user_id,
                career_id="software-developer",
                milestone_id="sd-version-control",
                status="in_progress",
            ),
            RoadmapProgress(
                user_id=user_id,
                career_id="unknown-career",
                milestone_id="ignored",
                status="completed",
            ),
        ])
        db_session.commit()

    content = client.get("/analytics").get_data(as_text=True)
    assert "Software Developer" in content
    assert "1 of 6 milestones completed." in content
    assert "17%" in content
    assert "unknown-career" not in content
