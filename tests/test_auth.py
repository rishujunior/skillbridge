import re

import pytest

from app import create_app


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


def register(client, **overrides):
    data = {
        "csrf_token": csrf_token(client, "/register"),
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "password": "correct-horse-battery-staple",
        "password_confirmation": "correct-horse-battery-staple",
    }
    data.update(overrides)
    return client.post("/register", data=data, follow_redirects=False)


def logout(client):
    return client.post("/logout", data={"csrf_token": csrf_token(client, "/dashboard")}, follow_redirects=False)


def test_registration_creates_an_authenticated_user(client):
    response = register(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    dashboard = client.get("/dashboard")
    assert b"Welcome, Ada Lovelace." in dashboard.data


def test_landing_and_authenticated_navigation_expose_visible_routes(client):
    landing = client.get("/")
    assert b'href="/login"' in landing.data
    assert b'href="/register"' in landing.data
    assert b"Create your account" in landing.data
    login = client.get("/login")
    assert b'class="app-sidebar"' not in login.data
    assert b'static/js/sidebar.js' not in login.data

    register(client)
    signed_in_landing = client.get("/")
    assert b"Go to dashboard" in signed_in_landing.data
    assert b'href="/dashboard"' in signed_in_landing.data

    dashboard = client.get("/dashboard")
    for destination in (
        b'href="/dashboard"',
        b'href="/profile"',
        b'href="/dashboard#skill-assessment"',
        b'href="/careers"',
        b'href="/roadmaps"',
        b'action="/logout"',
    ):
        assert destination in dashboard.data
    assert b'class="app-sidebar"' in dashboard.data
    assert b'class="sidebar-link is-active"' in dashboard.data
    assert b'static/js/sidebar.js' in dashboard.data

    profile = client.get("/profile")
    assert b'class="sidebar-link is-active"' in profile.data


def test_duplicate_email_is_rejected(client):
    register(client)
    logout(client)

    response = register(client, name="Another Student")
    assert response.status_code == 400
    assert b"An account with that email already exists." in response.data


def test_login_with_valid_credentials(client):
    register(client)
    logout(client)

    response = client.post(
        "/login",
        data={
            "csrf_token": csrf_token(client, "/login"),
            "email": "ada@example.com",
            "password": "correct-horse-battery-staple",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_login_welcome_notice_is_consumed_and_is_dismissible(client):
    register(client)
    logout(client)

    response = client.post(
        "/login",
        data={
            "csrf_token": csrf_token(client, "/login"),
            "email": "ada@example.com",
            "password": "correct-horse-battery-staple",
        },
        follow_redirects=False,
    )
    first_dashboard = client.get(response.headers["Location"])
    assert b"Welcome back." in first_dashboard.data
    assert b'data-auto-dismiss="7000"' in first_dashboard.data
    assert b'aria-label="Dismiss notification"' in first_dashboard.data

    second_dashboard = client.get("/dashboard")
    assert b"Welcome back." not in second_dashboard.data


def test_login_rejects_invalid_credentials(client):
    register(client)
    logout(client)

    response = client.post(
        "/login",
        data={
            "csrf_token": csrf_token(client, "/login"),
            "email": "ada@example.com",
            "password": "not-the-right-password",
        },
    )
    assert response.status_code == 400
    assert b"Email or password is incorrect." in response.data
    assert b'role="alert"' in response.data
    assert b'data-auto-dismiss' not in response.data


def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_logout_requires_post_and_valid_csrf_token(client):
    register(client)
    assert client.get("/logout").status_code == 405
    assert client.post("/logout", data={"csrf_token": "invalid"}).status_code == 400

    response = logout(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert client.get("/dashboard").status_code == 302
