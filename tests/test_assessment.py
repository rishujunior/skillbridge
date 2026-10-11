import re
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app import create_app
from assessment import QUESTIONS, calculate_scores
from models import AssessmentAnswer, AssessmentAttempt


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "DATABASE_URL": f"sqlite:///{tmp_path / 'test.sqlite3'}",
        }
    )
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
    return client.post(
        "/register",
        data={
            "csrf_token": csrf_token(client, "/register"),
            "name": name,
            "email": email,
            "password": "correct-horse-battery-staple",
            "password_confirmation": "correct-horse-battery-staple",
        },
        follow_redirects=False,
    )


def account_id(client):
    with client.session_transaction() as browser_session:
        return browser_session["user_id"]


def start_attempt(client):
    response = client.post(
        "/assessment/start",
        data={"csrf_token": csrf_token(client, "/dashboard")},
        follow_redirects=False,
    )
    assert response.status_code == 302
    match = re.search(r"/assessment/(\d+)/question/1$", response.headers["Location"])
    assert match
    return int(match.group(1))


def save_answer(client, attempt_id, position, answer, action="next"):
    path = f"/assessment/{attempt_id}/question/{position}"
    return client.post(
        path,
        data={"csrf_token": csrf_token(client, path), "answer": answer, "action": action},
        follow_redirects=False,
    )


def test_starting_assessment_and_saving_answer_persists_attempt(client, app):
    register(client)
    attempt_id = start_attempt(client)

    response = save_answer(client, attempt_id, 1, "b")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/assessment/{attempt_id}/question/2")

    with app.app_context():
        attempt = app.extensions["db_session"].get(AssessmentAttempt, attempt_id)
        answer = app.extensions["db_session"].scalar(select(AssessmentAnswer))
        assert attempt.status == "in_progress"
        assert answer.question_id == "programming_variables"
        assert answer.answer_value == "b"

    page = client.get(f"/assessment/{attempt_id}/question/1")
    assert b"checked" in page.data


def test_invalid_answer_is_rejected_and_incomplete_attempt_cannot_finish(client, app):
    register(client)
    attempt_id = start_attempt(client)

    invalid = save_answer(client, attempt_id, 1, "not-an-option")
    assert invalid.status_code == 400
    assert b"Choose an answer before continuing." in invalid.data

    final_question = QUESTIONS[-1]
    incomplete = save_answer(client, attempt_id, len(QUESTIONS), "a", action="finish")
    assert incomplete.status_code == 302
    assert incomplete.headers["Location"].endswith(f"/assessment/{attempt_id}/question/1")
    with app.app_context():
        assert app.extensions["db_session"].get(AssessmentAttempt, attempt_id).status == "in_progress"
        assert app.extensions["db_session"].scalar(select(AssessmentAnswer)).question_id == final_question["id"]


def test_scoring_rules_and_completed_results_are_persisted(client, app):
    register(client)
    attempt_id = start_attempt(client)
    answers = {question["id"]: "a" for question in QUESTIONS}
    for question in QUESTIONS:
        if "correct" in question:
            answers[question["id"]] = question["correct"]
    # Deliberately change objective answers to make each persisted category verifiable.
    answers["logic_sequence"] = "a"
    answers["logic_deduction"] = "a"
    answers["problem_debugging"] = "a"
    answers["problem_decomposition"] = "b"
    answers["problem_testing"] = "a"
    answers["analysis_data"] = "b"

    expected = calculate_scores(answers)
    assert expected == {
        "programming": 100,
        "logical_reasoning": 33,
        "problem_solving": 0,
        "analytical_thinking": 67,
        "overall": 50,
    }

    for position, question in enumerate(QUESTIONS, start=1):
        response = save_answer(
            client,
            attempt_id,
            position,
            answers[question["id"]],
            action="finish" if position == len(QUESTIONS) else "next",
        )
        assert response.status_code == 302

    assert response.headers["Location"].endswith(f"/assessment/{attempt_id}/results")
    with app.app_context():
        attempt = app.extensions["db_session"].get(AssessmentAttempt, attempt_id)
        assert attempt.status == "completed"
        assert attempt.completed_at is not None
        assert attempt.programming_score == 100
        assert attempt.logical_reasoning_score == 33
        assert attempt.problem_solving_score == 0
        assert attempt.analytical_thinking_score == 67
        assert attempt.overall_score == 50
        assert len(app.extensions["db_session"].scalars(select(AssessmentAnswer)).all()) == 15

    results = client.get(f"/assessment/{attempt_id}/results")
    assert b"Clear rules, no hidden analytics." in results.data
    assert b"100%" in results.data
    assert b"67%" in results.data
    assert b"This preference does not affect" not in results.data
    assert b'href="/careers"' in results.data
    assert b'href="/roadmaps"' in results.data


def test_attempts_and_results_are_private_to_their_owner(client, app):
    register(client)
    attempt_id = start_attempt(client)
    other_client = app.test_client()
    register(other_client, name="Grace Hopper", email="grace@example.com")

    assert other_client.get(f"/assessment/{attempt_id}/question/1").status_code == 404
    assert other_client.get(f"/assessment/{attempt_id}/results").status_code == 404


def test_results_handles_malformed_completed_attempt_without_error(client, app):
    register(client)
    with app.app_context():
        db_session = app.extensions["db_session"]
        attempt = AssessmentAttempt(
            user_id=account_id(client),
            status="completed",
            programming_score=None,
            logical_reasoning_score=67,
            problem_solving_score=67,
            analytical_thinking_score=67,
            overall_score=67,
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(attempt)
        db_session.commit()
        attempt_id = attempt.id

    response = client.get(f"/assessment/{attempt_id}/results")
    assert response.status_code == 200
    assert b"Assessment data is unavailable." in response.data
    assert b"Overall objective score:" not in response.data
    assert b"Start a new attempt" in response.data


def test_assessment_requires_login_and_valid_csrf(client):
    assert client.post("/assessment/start", data={}).status_code == 302
    register(client)
    assert client.post("/assessment/start", data={"csrf_token": "invalid"}).status_code == 400

    attempt_id = start_attempt(client)
    assert client.post(
        f"/assessment/{attempt_id}/question/1", data={"answer": "b", "csrf_token": "invalid"}
    ).status_code == 400
