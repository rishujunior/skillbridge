import json
import re

import pytest
from sqlalchemy import select

from app import create_app
from models import Resume, ResumeEntry, StudentProfile


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


def csrf_token(client, path="/resume"):
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


def user_id(client):
    with client.session_transaction() as browser_session:
        return browser_session["user_id"]


def resume_data(client, **overrides):
    data = {
        "csrf_token": csrf_token(client),
        "headline": "Junior software developer",
        "phone": "+91 90000 00000",
        "location": "Pune, India",
        "professional_summary": "I build accessible, useful software and keep learning.",
        "skills": "Python, Flask, Testing",
        "entry_type": ["project", "experience", "link"],
        "entry_title": ["SkillBridge", "Student developer", "Portfolio"],
        "entry_organization": ["Personal project", "Campus lab", ""],
        "entry_dates": ["2026", "2025 – 2026", ""],
        "entry_description": ["Built a student planning application.", "Helped test web features.", ""],
        "entry_url": ["https://example.com/skillbridge", "", "https://example.com/portfolio"],
    }
    data.update(overrides)
    return data


def test_resume_routes_require_login(client):
    for path in ("/resume", "/resume/preview", "/resume/download"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
    assert client.post("/resume", data={}, follow_redirects=False).status_code == 302


def test_builder_prefills_profile_and_navigation(client, app):
    register(client)
    with app.app_context():
        db_session = app.extensions["db_session"]
        db_session.add(StudentProfile(
            user_id=user_id(client), college="Analytical Engine University", degree="B.Sc.",
            branch="Computer Science", graduation_year=2028, career_goal="Backend Developer",
            career_interests="Python, databases", bio="I enjoy building reliable tools.",
        ))
        db_session.commit()

    page = client.get("/resume")
    assert page.status_code == 200
    assert b"Ada Lovelace" in page.data
    assert b"ada@example.com" in page.data
    assert b"Analytical Engine University" in page.data
    assert b'value="Backend Developer"' in page.data
    assert b"I enjoy building reliable tools." in page.data
    assert b">Resume Builder<" in page.data
    assert b'href="/resume"' in client.get("/dashboard").data


def test_resume_saves_edits_and_preserves_ordered_entries(client, app):
    register(client)
    response = client.post("/resume", data=resume_data(client), follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/resume")

    with app.app_context():
        db_session = app.extensions["db_session"]
        resume = db_session.scalar(select(Resume).where(Resume.user_id == user_id(client)))
        assert resume.headline == "Junior software developer"
        assert json.loads(resume.skills_json) == ["Python", "Flask", "Testing"]
        entries = db_session.scalars(select(ResumeEntry).order_by(ResumeEntry.sort_order)).all()
        assert [(entry.entry_type, entry.title) for entry in entries] == [
            ("project", "SkillBridge"), ("experience", "Student developer"), ("link", "Portfolio"),
        ]

    edited = resume_data(
        client,
        headline="QA engineer",
        skills="Python, Accessibility",
        entry_type=["certification"],
        entry_title=["Python certificate"],
        entry_organization=["SkillBridge Academy"],
        entry_dates=["2026"],
        entry_description=["Completed a practical Python programme."],
        entry_url=["https://example.com/certificate"],
    )
    assert client.post("/resume", data=edited, follow_redirects=False).status_code == 302
    with app.app_context():
        db_session = app.extensions["db_session"]
        resume = db_session.scalar(select(Resume).where(Resume.user_id == user_id(client)))
        assert resume.headline == "QA engineer"
        entries = db_session.scalars(select(ResumeEntry).order_by(ResumeEntry.sort_order)).all()
        assert [(entry.entry_type, entry.title) for entry in entries] == [("certification", "Python certificate")]


def test_resume_validation_and_csrf(client):
    register(client)
    assert client.post("/resume", data=resume_data(client, csrf_token="invalid")).status_code == 400
    response = client.post(
        "/resume",
        data=resume_data(client, entry_type=["link"], entry_title=["Portfolio"], entry_organization=[""], entry_dates=[""], entry_description=[""], entry_url=["javascript:alert(1)"]),
    )
    assert response.status_code == 400
    assert b"valid http:// or https:// URL" in response.data
    response = client.post(
        "/resume",
        data=resume_data(client, entry_type=["not-a-type"], entry_title=["Item"], entry_organization=[""], entry_dates=[""], entry_description=[""], entry_url=[""]),
    )
    assert response.status_code == 400
    assert b"valid resume entry type" in response.data
    response = client.post(
        "/resume",
        data=resume_data(
            client,
            entry_type=["project"] * 21,
            entry_title=["Small project"] * 21,
            entry_organization=[""] * 21,
            entry_dates=[""] * 21,
            entry_description=[""] * 21,
            entry_url=[""] * 21,
        ),
    )
    assert response.status_code == 400
    assert b"no more than 20 resume entries" in response.data


def test_resume_preview_and_pdf_are_saved_and_user_scoped(client, app):
    register(client)
    client.post("/resume", data=resume_data(client))
    preview = client.get("/resume/preview")
    assert preview.status_code == 200
    assert b"Junior software developer" in preview.data
    assert b"SkillBridge" in preview.data
    assert b"resume-document" in preview.data

    pdf = client.get("/resume/download")
    assert pdf.status_code == 200
    assert pdf.mimetype == "application/pdf"
    assert pdf.data.startswith(b"%PDF-")
    assert b"<html" not in pdf.data[:100]

    other_client = app.test_client()
    register(other_client, name="Grace Hopper", email="grace@example.com")
    other_preview = other_client.get("/resume/preview")
    assert b"Junior software developer" not in other_preview.data
    assert b"Built a student planning application." not in other_preview.data
    assert b"Ada Lovelace" not in other_preview.data
    assert other_client.get("/resume/download", follow_redirects=False).headers["Location"].endswith("/resume")
