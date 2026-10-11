import re

import pytest
from sqlalchemy import select

from app import create_app
from models import StudentProfile


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


def logout(client):
    return client.post("/logout", data={"csrf_token": csrf_token(client, "/dashboard")})


def profile_data(client, **overrides):
    data = {
        "csrf_token": csrf_token(client, "/profile"),
        "education_level": "Undergraduate",
        "college": "Analytical Engine University",
        "degree": "Bachelor of Science",
        "branch": "Computer Science",
        "graduation_year": "2028",
        "career_interests": "Software engineering, accessibility",
        "career_goal": "Accessibility engineer",
        "bio": "I enjoy designing useful tools for people.",
    }
    data.update(overrides)
    return data


def test_student_can_create_and_retrieve_profile(client, app):
    register(client)
    response = client.post("/profile", data=profile_data(client), follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    dashboard = client.get("/dashboard")
    assert b"Analytical Engine University" in dashboard.data
    assert b"Accessibility engineer" in dashboard.data
    assert b"100%" in dashboard.data

    with app.app_context():
        profile = app.extensions["db_session"].scalar(select(StudentProfile))
        assert profile.degree == "Bachelor of Science"
        assert profile.graduation_year == 2028


def test_student_can_edit_their_profile(client):
    register(client)
    client.post("/profile", data=profile_data(client))

    response = client.post(
        "/profile",
        data=profile_data(client, career_goal="Product designer", graduation_year="2029"),
        follow_redirects=False,
    )
    assert response.status_code == 302

    dashboard = client.get("/dashboard")
    assert b"Product designer" in dashboard.data
    assert b"Class of 2029" in dashboard.data


def test_profile_preserves_custom_degree_branch_and_career_goal_values(client, app):
    register(client)
    response = client.post(
        "/profile",
        data=profile_data(
            client,
            degree="Bachelor of Design",
            branch="Interaction Futures",
            career_goal="Experience Design Strategist",
            career_interests="Accessibility, service design, emerging technology",
        ),
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        profile = app.extensions["db_session"].scalar(select(StudentProfile))
        assert profile.degree == "Bachelor of Design"
        assert profile.branch == "Interaction Futures"
        assert profile.career_goal == "Experience Design Strategist"
        assert profile.career_interests == "Accessibility, service design, emerging technology"

    page = client.get("/profile")
    assert b'value="Bachelor of Design"' in page.data
    assert b'value="Interaction Futures"' in page.data
    assert b'value="Experience Design Strategist"' in page.data
    assert b'id="degree-suggestions"' in page.data
    assert b'id="career-goal-suggestions"' in page.data
    assert b'static/js/profile-suggestions.js' in page.data

    suggestions = client.get("/static/js/profile-suggestions.js")
    assert b'Computer Science and Engineering (CSE)' in suggestions.data
    assert b'"B.Tech / B.E."' in suggestions.data


def test_profile_is_scoped_to_the_authenticated_user(client, app):
    register(client, name="Ada Lovelace", email="ada@example.com")
    client.post("/profile", data=profile_data(client, career_goal="First user's goal"))
    logout(client)

    register(client, name="Grace Hopper", email="grace@example.com")
    page = client.get("/profile")
    assert b"First user&#39;s goal" not in page.data

    client.post("/profile", data=profile_data(client, career_goal="Second user's goal"))

    with app.app_context():
        profiles = app.extensions["db_session"].scalars(select(StudentProfile).order_by(StudentProfile.id)).all()
        assert len(profiles) == 2
        assert [profile.career_goal for profile in profiles] == ["First user's goal", "Second user's goal"]


def test_profile_validation_rejects_invalid_year(client):
    register(client)
    response = client.post("/profile", data=profile_data(client, graduation_year="1800"))
    assert response.status_code == 400
    assert b"Enter a graduation year between 1900 and 15 years from now." in response.data


def test_profile_routes_require_login(client):
    assert client.get("/profile", follow_redirects=False).status_code == 302
    assert client.post("/profile", data={}, follow_redirects=False).status_code == 302
