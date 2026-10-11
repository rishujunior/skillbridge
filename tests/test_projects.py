import json
import re

import pytest
from sqlalchemy import select

from app import create_app
from models import StudentProject


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


def project_data(client, path="/projects/new", **overrides):
    data = {
        "csrf_token": csrf_token(client, path),
        "title": "SkillBridge planner",
        "description": "A private student planning application with accessible forms.",
        "technologies": "Python, Flask, SQLite, Python",
        "github_url": "https://github.com/ada/skillbridge-planner",
        "live_demo_url": "https://demo.example.com/skillbridge",
        "image_url": "https://images.example.com/skillbridge.png",
    }
    data.update(overrides)
    return data


def add_project(app, user_id, title="Private project"):
    with app.app_context():
        db_session = app.extensions["db_session"]
        project = StudentProject(
            user_id=user_id,
            title=title,
            description="A project owned by one student.",
            technologies_json=json.dumps(["Python"]),
            github_url="https://github.com/owner/private-project",
        )
        db_session.add(project)
        db_session.commit()
        return project.id


def test_project_routes_require_login(client):
    for path in ("/projects", "/projects/new", "/projects/1/edit", "/projects/1/delete"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
    assert client.post("/projects/new", data={}, follow_redirects=False).status_code == 302


def test_projects_empty_state_sidebar_and_dashboard_entry(client):
    register(client)
    page = client.get("/projects")
    assert page.status_code == 200
    assert b"Your portfolio starts with one project." in page.data
    assert b">Project Portfolio<" in page.data
    dashboard = client.get("/dashboard")
    assert b'href="/projects"' in dashboard.data
    assert b"Showcase projects" in dashboard.data


def test_student_can_create_edit_and_list_own_projects(client, app):
    register(client)
    response = client.post("/projects/new", data=project_data(client), follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/projects")

    with app.app_context():
        db_session = app.extensions["db_session"]
        project = db_session.scalar(select(StudentProject).where(StudentProject.user_id == account_id(client)))
        project_id = project.id
        assert json.loads(project.technologies_json) == ["Python", "Flask", "SQLite"]
        assert project.live_demo_url == "https://demo.example.com/skillbridge"

    page = client.get("/projects")
    assert b"SkillBridge planner" in page.data
    assert b"Flask" in page.data
    assert b'target="_blank" rel="noopener noreferrer"' in page.data
    assert b'referrerpolicy="no-referrer"' in page.data

    response = client.post(
        f"/projects/{project_id}/edit",
        data=project_data(
            client,
            f"/projects/{project_id}/edit",
            title="Updated project",
            technologies="Python, Testing",
            live_demo_url="",
            image_url="",
        ),
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app.app_context():
        project = app.extensions["db_session"].get(StudentProject, project_id)
        assert project.title == "Updated project"
        assert json.loads(project.technologies_json) == ["Python", "Testing"]
        assert project.live_demo_url is None


def test_project_validation_and_csrf(client):
    register(client)
    assert client.post("/projects/new", data=project_data(client, csrf_token="invalid")).status_code == 400

    invalid_github = client.post(
        "/projects/new",
        data=project_data(client, github_url="http://github.com/ada/skillbridge-planner"),
    )
    assert invalid_github.status_code == 400
    assert b"canonical HTTPS GitHub repository URL" in invalid_github.data
    invalid_live_demo = client.post(
        "/projects/new",
        data=project_data(client, live_demo_url="javascript:alert(1)"),
    )
    assert invalid_live_demo.status_code == 400
    assert b"Live demo URL must use a valid http:// or https:// URL" in invalid_live_demo.data
    missing_technologies = client.post("/projects/new", data=project_data(client, technologies=""))
    assert missing_technologies.status_code == 400
    assert b"Add at least one technology" in missing_technologies.data


def test_project_ownership_delete_confirmation_and_deletion(client, app):
    register(client)
    first_user_id = account_id(client)
    project_id = add_project(app, first_user_id, title="First student's work")

    other_client = app.test_client()
    register(other_client, name="Grace Hopper", email="grace@example.com")
    for path in (f"/projects/{project_id}/edit", f"/projects/{project_id}/delete"):
        assert other_client.get(path).status_code == 404
        assert other_client.post(path, data={"csrf_token": csrf_token(other_client, "/projects")}).status_code == 404
    assert b"First student&#39;s work" not in other_client.get("/projects").data

    confirmation = client.get(f"/projects/{project_id}/delete")
    assert confirmation.status_code == 200
    assert b"Confirm deletion" in confirmation.data
    assert b"First student&#39;s work" in confirmation.data
    response = client.post(
        f"/projects/{project_id}/delete",
        data={"csrf_token": csrf_token(client, f"/projects/{project_id}/delete")},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app.app_context():
        assert app.extensions["db_session"].get(StudentProject, project_id) is None
