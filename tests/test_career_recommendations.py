import re
from datetime import datetime, timezone

import pytest

from app import create_app
from career_recommendations import build_recommendations
from models import AssessmentAnswer, AssessmentAttempt


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
    client.post("/register", data={
        "csrf_token": csrf_token(client, "/register"), "name": name, "email": email,
        "password": "correct-horse-battery-staple", "password_confirmation": "correct-horse-battery-staple",
    })


def add_completed_attempt(app, account_id, scores=None, answers=None):
    scores = scores or {"programming": 100, "logical_reasoning": 75, "problem_solving": 75, "analytical_thinking": 50}
    answers = answers or {"interest_activity": "a", "interest_problem": "a", "interest_learning": "a"}
    with app.app_context():
        session = app.extensions["db_session"]
        attempt = AssessmentAttempt(
            user_id=account_id, status="completed", programming_score=scores.get("programming"),
            logical_reasoning_score=scores.get("logical_reasoning"), problem_solving_score=scores.get("problem_solving"),
            analytical_thinking_score=scores.get("analytical_thinking"), overall_score=75,
            completed_at=datetime.now(timezone.utc),
        )
        session.add(attempt)
        session.flush()
        for question_id, value in answers.items():
            session.add(AssessmentAnswer(attempt_id=attempt.id, question_id=question_id, answer_value=value))
        session.commit()
        return attempt.id


def user_id(client):
    with client.session_transaction() as session:
        return session["user_id"]


def test_recommendations_have_deterministic_rank_and_explicit_weighted_score():
    scores = {"programming": 100, "logical_reasoning": 50, "problem_solving": 75, "analytical_thinking": 25}
    answers = {"interest_activity": "a", "interest_problem": "a", "interest_learning": "a"}
    recommendations = build_recommendations(scores, answers)
    software = next(item for item in recommendations if item["name"] == "Software Developer")
    assert recommendations[0]["name"] == "Software Developer"
    # (100*.45 + 75*.30 + 50*.15 + 25*.10) * .80 + 100 * .20 = 82
    assert software["objective_fit"] == 78
    assert software["interest_fit"] == 100
    assert software["match_score"] == 82
    assert software["skill_weights"][0] == {"label": "Programming fundamentals", "percentage": 45}
    assert recommendations == build_recommendations(scores, answers)


def test_interests_adjust_alignment_without_changing_objective_ability_or_skill_gaps():
    scores = {"programming": 100, "logical_reasoning": 100, "problem_solving": 40, "analytical_thinking": 100}
    aligned = build_recommendations(scores, {"interest_activity": "a", "interest_problem": "a", "interest_learning": "a"})
    unaligned = build_recommendations(scores, {"interest_activity": "d", "interest_problem": "d", "interest_learning": "d"})
    aligned_software = next(item for item in aligned if item["name"] == "Software Developer")
    unaligned_software = next(item for item in unaligned if item["name"] == "Software Developer")
    assert aligned_software["objective_fit"] == unaligned_software["objective_fit"]
    assert aligned_software["match_score"] - unaligned_software["match_score"] == 20
    gap = next(gap for gap in aligned_software["skill_gaps"] if gap["category"] == "problem_solving")
    assert gap["score"] == 40
    assert gap["gap"] == 30


def test_recommendation_engine_rejects_absent_or_invalid_scores():
    with pytest.raises(ValueError, match="unavailable"):
        build_recommendations(None, {"interest_activity": "a"})
    with pytest.raises(ValueError, match="invalid"):
        build_recommendations({"programming": 101, "logical_reasoning": 0, "problem_solving": 0, "analytical_thinking": 0}, {"interest_activity": "a"})


def test_careers_empty_state_and_incomplete_profile_context(client, app):
    register(client)
    no_assessment = client.get("/careers")
    assert no_assessment.status_code == 200
    assert b"Complete an assessment first." in no_assessment.data
    add_completed_attempt(app, user_id(client))
    recommendations = client.get("/careers")
    assert b"Recommendations are provisional." in recommendations.data
    assert b"Software Developer" in recommendations.data
    assert b"Relevant objective weights" in recommendations.data
    assert b"Profile information does not change the match percentages." in recommendations.data
    assert b'href="/roadmaps/software-developer"' in recommendations.data


def test_careers_are_authenticated_and_scoped_to_current_user(client, app):
    assert client.get("/careers", follow_redirects=False).status_code == 302
    register(client)
    add_completed_attempt(app, user_id(client))
    other_client = app.test_client()
    register(other_client, name="Grace Hopper", email="grace@example.com")
    other_page = other_client.get("/careers")
    assert b"Complete an assessment first." in other_page.data
    assert b"Software Developer" not in other_page.data


def test_careers_honestly_handles_invalid_persisted_assessment_data(client, app):
    register(client)
    add_completed_attempt(app, user_id(client), scores={"programming": None, "logical_reasoning": 50, "problem_solving": 50, "analytical_thinking": 50})
    page = client.get("/careers")
    assert page.status_code == 200
    assert b"This assessment cannot be used yet." in page.data
    assert b"Software Developer" not in page.data
