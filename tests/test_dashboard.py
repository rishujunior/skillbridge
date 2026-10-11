import re
from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from career_recommendations import build_recommendations
from models import AssessmentAnswer, AssessmentAttempt, RoadmapProgress, StudentProfile


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
    assert match
    return match.group(1)


def register(client, name="Ada Lovelace", email="ada@example.com"):
    client.post("/register", data={
        "csrf_token": csrf_token(client, "/register"),
        "name": name,
        "email": email,
        "password": "correct-horse-battery-staple",
        "password_confirmation": "correct-horse-battery-staple",
    })


def account_id(client):
    with client.session_transaction() as browser_session:
        return browser_session["user_id"]


def add_completed_attempt(app, user_id, scores=None, answers=None, overall_score=75, completed_at=None):
    scores = scores or {
        "programming": 100,
        "logical_reasoning": 75,
        "problem_solving": 75,
        "analytical_thinking": 50,
    }
    answers = answers or {
        "interest_activity": "a",
        "interest_problem": "a",
        "interest_learning": "a",
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
        db_session.flush()
        for question_id, value in answers.items():
            db_session.add(AssessmentAnswer(attempt_id=attempt.id, question_id=question_id, answer_value=value))
        db_session.commit()
        return attempt.id


def test_dashboard_requires_authentication(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_first_time_dashboard_uses_honest_empty_states(client):
    register(client)
    page = client.get("/dashboard")
    content = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "0%" in content
    assert "Start with your education, interests, and career goal." in content
    assert "No assessment yet" in content
    assert "No roadmap activity yet" in content
    assert "Complete an assessment to see career matches." in content


def test_dashboard_shows_actual_profile_completion_and_summary(client, app):
    register(client)
    with app.app_context():
        db_session = app.extensions["db_session"]
        db_session.add(StudentProfile(
            user_id=account_id(client), degree="B.Sc.", branch="Mathematics", career_goal="Data Analyst"
        ))
        db_session.commit()

    content = client.get("/dashboard").get_data(as_text=True)
    assert "38%" in content
    assert "B.Sc." in content
    assert "Mathematics" in content
    assert "Data Analyst" in content


def test_dashboard_uses_latest_completed_score_and_top_three_matches(client, app):
    register(client)
    user_id = account_id(client)
    answers = {"interest_activity": "a", "interest_problem": "a", "interest_learning": "a"}
    add_completed_attempt(
        app, user_id, overall_score=31, completed_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    scores = {"programming": 90, "logical_reasoning": 60, "problem_solving": 80, "analytical_thinking": 70}
    add_completed_attempt(app, user_id, scores=scores, answers=answers, overall_score=77)

    content = client.get("/dashboard").get_data(as_text=True)
    assert "Overall score: <strong>77%</strong>" in content
    assert "Overall score: <strong>31%</strong>" not in content
    expected = build_recommendations(scores, answers)[:3]
    for recommendation in expected:
        assert recommendation["name"] in content
        assert f'>{recommendation["match_score"]}%</strong><span>match</span>' in content
        assert f'href="/roadmaps/{recommendation["id"]}"' in content


def test_dashboard_continues_in_progress_attempt(client, app):
    register(client)
    with app.app_context():
        db_session = app.extensions["db_session"]
        attempt = AssessmentAttempt(user_id=account_id(client), status="in_progress")
        db_session.add(attempt)
        db_session.commit()
        attempt_id = attempt.id

    content = client.get("/dashboard").get_data(as_text=True)
    assert "Continue your assessment" in content
    assert f'href="/assessment/{attempt_id}/question/1"' in content


def test_dashboard_honestly_handles_invalid_completed_assessment_data(client, app):
    register(client)
    add_completed_attempt(
        app,
        account_id(client),
        scores={"programming": None, "logical_reasoning": 60, "problem_solving": 60, "analytical_thinking": 60},
    )
    content = client.get("/dashboard").get_data(as_text=True)
    assert "Assessment results unavailable" in content
    assert "Career matches are unavailable" in content
    assert "Your strongest rule-based alignments." in content
    assert "Software Developer" not in content


def test_dashboard_uses_current_users_latest_valid_roadmap_progress(client, app):
    register(client)
    first_user_id = account_id(client)
    add_completed_attempt(app, first_user_id)
    with app.app_context():
        db_session = app.extensions["db_session"]
        db_session.add_all([
            RoadmapProgress(user_id=first_user_id, career_id="software-developer", milestone_id="sd-python-basics", status="completed"),
            RoadmapProgress(user_id=first_user_id, career_id="software-developer", milestone_id="sd-version-control", status="in_progress"),
        ])
        db_session.commit()

    first_content = client.get("/dashboard").get_data(as_text=True)
    assert "Software Developer" in first_content
    assert "1 of 6 milestones completed." in first_content
    assert "17%" in first_content
    assert 'href="/roadmaps/software-developer"' in first_content

    other_client = app.test_client()
    register(other_client, name="Grace Hopper", email="grace@example.com")
    add_completed_attempt(app, account_id(other_client))
    other_content = other_client.get("/dashboard").get_data(as_text=True)
    assert "No roadmap activity yet" in other_content
    assert "1 of 6 milestones completed." not in other_content


def test_dashboard_does_not_fabricate_roadmap_progress(client, app):
    register(client)
    add_completed_attempt(app, account_id(client))
    content = client.get("/dashboard").get_data(as_text=True)
    assert "No roadmap activity yet" in content
    assert "Choose a roadmap" in content
    assert "milestones completed." not in content
