import os
import re
import secrets
import json
from datetime import datetime
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, Response, abort, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

from assessment import CATEGORY_LABELS, OBJECTIVE_CATEGORIES, QUESTIONS, calculate_scores, option_label
from career_recommendations import build_recommendations
from models import AssessmentAnswer, AssessmentAttempt, Base, Resume, ResumeEntry, RoadmapProgress, StudentProfile, StudentProject, User
from roadmaps import VALID_PROGRESS_STATUSES, milestones_for, progress_summary, roadmap_for
from weasyprint import CSS, HTML


RESUME_ENTRY_TYPES = ("project", "experience", "certification", "link")
MAX_RESUME_ENTRIES = 20
MAX_PROJECT_TECHNOLOGIES = 25


def create_app(test_config=None):
    """Create the SkillBridge web application."""
    app = Flask(__name__, instance_relative_config=True)
    is_production = os.environ.get("SKILLBRIDGE_ENV") == "production"
    configured_secret = os.environ.get("SKILLBRIDGE_SECRET_KEY")
    if is_production and not configured_secret:
        raise RuntimeError("SKILLBRIDGE_SECRET_KEY must be set in production.")

    app.config.from_mapping(
        SECRET_KEY=configured_secret or secrets.token_urlsafe(32),
        DATABASE_URL=os.environ.get(
            "SKILLBRIDGE_DATABASE_URL",
            f"sqlite:///{Path(app.instance_path) / 'skillbridge.sqlite3'}",
        ),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=is_production,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    database_url = app.config["DATABASE_URL"]
    engine_options = {"future": True}
    if database_url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
    engine = create_engine(database_url, **engine_options)
    db_session = scoped_session(sessionmaker(bind=engine, autoflush=False, expire_on_commit=False))
    Base.metadata.create_all(engine)
    app.extensions["db_session"] = db_session

    @app.teardown_appcontext
    def close_database(_error=None):
        db_session.remove()

    def csrf_token():
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token

    @app.context_processor
    def inject_template_helpers():
        return {"csrf_token": csrf_token}

    @app.before_request
    def load_logged_in_user():
        g.user = None
        user_id = session.get("user_id")
        if user_id:
            g.user = db_session.get(User, user_id)
            if g.user is None:
                session.clear()

    def login_required(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if g.user is None:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped_view

    def csrf_protected(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                submitted_token = request.form.get("csrf_token", "")
                expected_token = session.get("csrf_token", "")
                if not expected_token or not secrets.compare_digest(submitted_token, expected_token):
                    abort(400, "Invalid or missing CSRF token.")
            return view(*args, **kwargs)

        return wrapped_view

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/register", methods=("GET", "POST"))
    def register():
        if g.user:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            submitted_token = request.form.get("csrf_token", "")
            if not secrets.compare_digest(submitted_token, session.get("csrf_token", "")):
                abort(400, "Invalid or missing CSRF token.")

            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            password_confirmation = request.form.get("password_confirmation", "")
            errors = []

            if len(name) < 2 or len(name) > 100:
                errors.append("Enter a name between 2 and 100 characters.")
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                errors.append("Enter a valid email address.")
            if len(password) < 8:
                errors.append("Password must be at least 8 characters.")
            if password != password_confirmation:
                errors.append("Password confirmation does not match.")
            if db_session.scalar(select(User).where(User.email == email)):
                errors.append("An account with that email already exists.")

            if errors:
                for error in errors:
                    flash(error, "error")
                return render_template("auth/register.html"), 400

            user = User(name=name, email=email, password_hash=generate_password_hash(password))
            db_session.add(user)
            try:
                db_session.commit()
            except IntegrityError:
                db_session.rollback()
                flash("An account with that email already exists.", "error")
                return render_template("auth/register.html"), 400

            session.clear()
            session["user_id"] = user.id
            csrf_token()
            flash("Welcome to SkillBridge.", "success")
            return redirect(url_for("dashboard"))

        return render_template("auth/register.html")

    @app.route("/login", methods=("GET", "POST"))
    def login():
        if g.user:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            submitted_token = request.form.get("csrf_token", "")
            if not secrets.compare_digest(submitted_token, session.get("csrf_token", "")):
                abort(400, "Invalid or missing CSRF token.")

            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = db_session.scalar(select(User).where(User.email == email))
            if user is None or not check_password_hash(user.password_hash, password):
                flash("Email or password is incorrect.", "error")
                return render_template("auth/login.html"), 400

            session.clear()
            session["user_id"] = user.id
            csrf_token()
            flash("Welcome back.", "success")
            return redirect(url_for("dashboard"))

        return render_template("auth/login.html")

    @app.get("/dashboard")
    @login_required
    def dashboard():
        profile = db_session.scalar(select(StudentProfile).where(StudentProfile.user_id == g.user.id))
        completion = profile.completion_percentage() if profile else 0
        in_progress_attempt = db_session.scalar(
            select(AssessmentAttempt)
            .where(AssessmentAttempt.user_id == g.user.id, AssessmentAttempt.status == "in_progress")
            .order_by(AssessmentAttempt.updated_at.desc())
        )
        latest_completed_attempt, recommendations = latest_recommendations_for_user(g.user.id)
        latest_completed_score = None
        if latest_completed_attempt and isinstance(latest_completed_attempt.overall_score, int):
            if 0 <= latest_completed_attempt.overall_score <= 100:
                latest_completed_score = latest_completed_attempt.overall_score

        # Load every saved progress row once, then keep only rows that still point
        # to a real roadmap milestone. This makes the dashboard resilient to stale
        # SQLite records without exposing another user's progress.
        progress_rows = db_session.scalars(
            select(RoadmapProgress)
            .where(RoadmapProgress.user_id == g.user.id)
            .order_by(RoadmapProgress.updated_at.desc())
        ).all()
        roadmap_statuses = {}
        latest_roadmap_id = None
        for row in progress_rows:
            roadmap = roadmap_for(row.career_id)
            if roadmap is None or row.status not in VALID_PROGRESS_STATUSES:
                continue
            milestone_ids = {item["id"] for item in milestones_for(roadmap)}
            if row.milestone_id not in milestone_ids:
                continue
            statuses = roadmap_statuses.setdefault(row.career_id, {})
            statuses.setdefault(row.milestone_id, row.status)
            if latest_roadmap_id is None:
                latest_roadmap_id = row.career_id

        active_roadmap = None
        if latest_roadmap_id:
            roadmap = roadmap_for(latest_roadmap_id)
            active_roadmap = {
                "id": latest_roadmap_id,
                "name": roadmap["career_name"],
                "summary": progress_summary(roadmap, roadmap_statuses[latest_roadmap_id]),
                "is_available": bool(recommendations),
            }
        return render_template(
            "dashboard.html",
            profile=profile,
            completion=completion,
            in_progress_attempt=in_progress_attempt,
            latest_completed_attempt=latest_completed_attempt,
            latest_completed_score=latest_completed_score,
            recommendations=recommendations,
            top_recommendations=(recommendations or [])[:3],
            assessment_data_issue=latest_completed_attempt is not None and recommendations is None,
            active_roadmap=active_roadmap,
        )

    def owned_attempt(attempt_id, require_in_progress=False):
        attempt = db_session.get(AssessmentAttempt, attempt_id)
        if attempt is None or attempt.user_id != g.user.id:
            abort(404)
        if require_in_progress and attempt.status != "in_progress":
            abort(404)
        return attempt

    def answer_map(attempt_id):
        answers = db_session.scalars(
            select(AssessmentAnswer).where(AssessmentAnswer.attempt_id == attempt_id)
        ).all()
        return {answer.question_id: answer.answer_value for answer in answers}

    def latest_recommendations_for_user(user_id):
        attempt = db_session.scalar(
            select(AssessmentAttempt)
            .where(AssessmentAttempt.user_id == user_id, AssessmentAttempt.status == "completed")
            .order_by(AssessmentAttempt.completed_at.desc())
        )
        if attempt is None:
            return None, None
        scores = {
            "programming": attempt.programming_score,
            "logical_reasoning": attempt.logical_reasoning_score,
            "problem_solving": attempt.problem_solving_score,
            "analytical_thinking": attempt.analytical_thinking_score,
        }
        try:
            return attempt, build_recommendations(scores, answer_map(attempt.id))
        except ValueError:
            return attempt, None

    @app.post("/assessment/start")
    @login_required
    @csrf_protected
    def start_assessment():
        attempt = db_session.scalar(
            select(AssessmentAttempt)
            .where(AssessmentAttempt.user_id == g.user.id, AssessmentAttempt.status == "in_progress")
            .order_by(AssessmentAttempt.updated_at.desc())
        )
        if attempt is None:
            attempt = AssessmentAttempt(user_id=g.user.id)
            db_session.add(attempt)
            db_session.commit()
        return redirect(url_for("assessment_question", attempt_id=attempt.id, position=1))

    @app.route("/assessment/<int:attempt_id>/question/<int:position>", methods=("GET", "POST"))
    @login_required
    @csrf_protected
    def assessment_question(attempt_id, position):
        attempt = owned_attempt(attempt_id, require_in_progress=True)
        if not 1 <= position <= len(QUESTIONS):
            abort(404)
        question = QUESTIONS[position - 1]
        answers = answer_map(attempt.id)

        if request.method == "POST":
            selected_answer = request.form.get("answer", "")
            valid_options = {value for value, _label in question["options"]}
            if selected_answer not in valid_options:
                flash("Choose an answer before continuing.", "error")
                return render_template(
                    "assessment/question.html", attempt=attempt, question=question, position=position,
                    total_questions=len(QUESTIONS), selected_answer=answers.get(question["id"]),
                ), 400

            stored_answer = db_session.scalar(
                select(AssessmentAnswer).where(
                    AssessmentAnswer.attempt_id == attempt.id,
                    AssessmentAnswer.question_id == question["id"],
                )
            )
            if stored_answer is None:
                db_session.add(AssessmentAnswer(
                    attempt_id=attempt.id, question_id=question["id"], answer_value=selected_answer
                ))
            else:
                stored_answer.answer_value = selected_answer
            db_session.commit()

            action = request.form.get("action", "next")
            if action == "previous":
                target = max(1, position - 1)
                return redirect(url_for("assessment_question", attempt_id=attempt.id, position=target))
            if action == "finish":
                completed_answers = answer_map(attempt.id)
                missing = next((index for index, item in enumerate(QUESTIONS, start=1) if item["id"] not in completed_answers), None)
                if missing:
                    flash("Answer every question before submitting your assessment.", "error")
                    return redirect(url_for("assessment_question", attempt_id=attempt.id, position=missing))
                scores = calculate_scores(completed_answers)
                attempt.programming_score = scores["programming"]
                attempt.logical_reasoning_score = scores["logical_reasoning"]
                attempt.problem_solving_score = scores["problem_solving"]
                attempt.analytical_thinking_score = scores["analytical_thinking"]
                attempt.overall_score = scores["overall"]
                attempt.status = "completed"
                attempt.completed_at = datetime.now().astimezone()
                db_session.commit()
                flash("Assessment complete. Review your results below.", "success")
                return redirect(url_for("assessment_results", attempt_id=attempt.id))
            return redirect(url_for("assessment_question", attempt_id=attempt.id, position=min(position + 1, len(QUESTIONS))))

        return render_template(
            "assessment/question.html", attempt=attempt, question=question, position=position,
            total_questions=len(QUESTIONS), selected_answer=answers.get(question["id"]),
        )

    @app.get("/assessment/<int:attempt_id>/results")
    @login_required
    def assessment_results(attempt_id):
        attempt = owned_attempt(attempt_id)
        if attempt.status != "completed":
            return redirect(url_for("assessment_question", attempt_id=attempt.id, position=1))
        scores = {
            "programming": attempt.programming_score,
            "logical_reasoning": attempt.logical_reasoning_score,
            "problem_solving": attempt.problem_solving_score,
            "analytical_thinking": attempt.analytical_thinking_score,
        }
        strengths = [category for category in OBJECTIVE_CATEGORIES if scores[category] >= 67]
        improvement_areas = [category for category in OBJECTIVE_CATEGORIES if scores[category] < 67]
        answers = answer_map(attempt.id)
        interests = [
            {"prompt": question["prompt"], "answer": option_label(question, answers.get(question["id"]))}
            for question in QUESTIONS if question["category"] == "interests"
        ]
        return render_template(
            "assessment/results.html", attempt=attempt, scores=scores, category_labels=CATEGORY_LABELS,
            strengths=strengths, improvement_areas=improvement_areas, interests=interests,
        )

    @app.get("/careers")
    @login_required
    def career_recommendations():
        profile = db_session.scalar(select(StudentProfile).where(StudentProfile.user_id == g.user.id))
        attempt, recommendations = latest_recommendations_for_user(g.user.id)
        if attempt is None:
            return render_template("careers.html", attempt=None, profile=profile, recommendations=[])
        if recommendations is None:
            return render_template(
                "careers.html", attempt=attempt, profile=profile, recommendations=[], data_issue=True
            )
        return render_template(
            "careers.html", attempt=attempt, profile=profile, recommendations=recommendations
        )

    @app.get("/roadmaps")
    @login_required
    def roadmaps():
        attempt, recommendations = latest_recommendations_for_user(g.user.id)
        return render_template(
            "roadmaps/index.html", attempt=attempt, recommendations=recommendations or [],
            data_issue=attempt is not None and recommendations is None,
        )

    def selected_roadmap_for_user(career_id):
        attempt, recommendations = latest_recommendations_for_user(g.user.id)
        if attempt is None or recommendations is None:
            abort(404)
        recommendation = next((item for item in recommendations if item["id"] == career_id), None)
        roadmap = roadmap_for(career_id)
        if recommendation is None or roadmap is None:
            abort(404)
        return roadmap, recommendation

    @app.get("/roadmaps/<career_id>")
    @login_required
    def roadmap_detail(career_id):
        roadmap, recommendation = selected_roadmap_for_user(career_id)
        progress_rows = db_session.scalars(
            select(RoadmapProgress).where(
                RoadmapProgress.user_id == g.user.id, RoadmapProgress.career_id == career_id
            )
        ).all()
        statuses = {row.milestone_id: row.status for row in progress_rows}
        return render_template(
            "roadmaps/detail.html", roadmap=roadmap, recommendation=recommendation, statuses=statuses,
            summary=progress_summary(roadmap, statuses), valid_statuses=VALID_PROGRESS_STATUSES,
        )

    @app.post("/roadmaps/<career_id>/milestones/<milestone_id>/progress")
    @login_required
    @csrf_protected
    def update_roadmap_progress(career_id, milestone_id):
        roadmap, _recommendation = selected_roadmap_for_user(career_id)
        valid_milestones = {item["id"] for item in milestones_for(roadmap)}
        if milestone_id not in valid_milestones:
            abort(404)
        status = request.form.get("status", "")
        if status not in VALID_PROGRESS_STATUSES:
            abort(400, "Choose a valid milestone status.")
        progress = db_session.scalar(
            select(RoadmapProgress).where(
                RoadmapProgress.user_id == g.user.id,
                RoadmapProgress.career_id == career_id,
                RoadmapProgress.milestone_id == milestone_id,
            )
        )
        if progress is None:
            progress = RoadmapProgress(
                user_id=g.user.id, career_id=career_id, milestone_id=milestone_id, status=status
            )
            db_session.add(progress)
        else:
            progress.status = status
        db_session.commit()
        flash("Milestone progress saved.", "success")
        return redirect(url_for("roadmap_detail", career_id=career_id, _anchor="stage-" + next(
            stage["id"] for stage in roadmap["stages"] if any(item["id"] == milestone_id for item in stage["milestones"])
        )))

    def resume_for_user(user_id):
        return db_session.scalar(select(Resume).where(Resume.user_id == user_id))

    def resume_entries_for_user(resume):
        if resume is None:
            return []
        return db_session.scalars(
            select(ResumeEntry)
            .where(ResumeEntry.resume_id == resume.id)
            .order_by(ResumeEntry.sort_order, ResumeEntry.id)
        ).all()

    def resume_skills(resume):
        if resume is None or not resume.skills_json:
            return []
        try:
            skills = json.loads(resume.skills_json)
        except (TypeError, json.JSONDecodeError):
            return []
        return [skill for skill in skills if isinstance(skill, str) and skill.strip()]

    def resume_context():
        profile = db_session.scalar(select(StudentProfile).where(StudentProfile.user_id == g.user.id))
        resume = resume_for_user(g.user.id)
        return {
            "profile": profile,
            "resume": resume,
            "entries": resume_entries_for_user(resume),
            "skills": resume_skills(resume),
            "entry_types": RESUME_ENTRY_TYPES,
        }

    def valid_resume_url(value):
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def project_technologies(project):
        try:
            technologies = json.loads(project.technologies_json)
        except (AttributeError, TypeError, json.JSONDecodeError):
            return []
        return [item for item in technologies if isinstance(item, str) and item.strip()]

    def owned_project(project_id):
        project = db_session.scalar(
            select(StudentProject).where(
                StudentProject.id == project_id, StudentProject.user_id == g.user.id
            )
        )
        if project is None:
            abort(404)
        return project

    def valid_github_repository_url(value):
        parsed = urlparse(value)
        path_parts = [part for part in parsed.path.split("/") if part]
        return (
            parsed.scheme == "https"
            and parsed.hostname == "github.com"
            and len(path_parts) == 2
            and not parsed.params
            and not parsed.query
            and not parsed.fragment
        )

    def project_form_values(project=None):
        if project is None:
            return {
                "title": "", "description": "", "technologies": "", "github_url": "",
                "live_demo_url": "", "image_url": "",
            }
        return {
            "title": project.title,
            "description": project.description,
            "technologies": ", ".join(project_technologies(project)),
            "github_url": project.github_url,
            "live_demo_url": project.live_demo_url or "",
            "image_url": project.image_url or "",
        }

    def submitted_project_values():
        values = {
            "title": request.form.get("title", "").strip(),
            "description": request.form.get("description", "").strip(),
            "technologies": request.form.get("technologies", "").strip(),
            "github_url": request.form.get("github_url", "").strip(),
            "live_demo_url": request.form.get("live_demo_url", "").strip(),
            "image_url": request.form.get("image_url", "").strip(),
        }
        errors = []
        if not values["title"]:
            errors.append("Project title is required.")
        if not values["description"]:
            errors.append("Project description is required.")
        for key, label, maximum in (
            ("title", "Project title", 160),
            ("description", "Project description", 4000),
            ("technologies", "Technologies", 1000),
            ("github_url", "GitHub repository URL", 500),
            ("live_demo_url", "Live demo URL", 500),
            ("image_url", "Project image URL", 500),
        ):
            if len(values[key]) > maximum:
                errors.append(f"{label} must be {maximum} characters or fewer.")

        technologies = []
        seen_technologies = set()
        for technology in values["technologies"].replace("\n", ",").split(","):
            technology = technology.strip()
            normalized = technology.casefold()
            if technology and normalized not in seen_technologies:
                technologies.append(technology)
                seen_technologies.add(normalized)
        if not technologies:
            errors.append("Add at least one technology used in this project.")
        if len(technologies) > MAX_PROJECT_TECHNOLOGIES or any(len(item) > 80 for item in technologies):
            errors.append(f"Add up to {MAX_PROJECT_TECHNOLOGIES} technologies, with no technology longer than 80 characters.")
        if not valid_github_repository_url(values["github_url"]):
            errors.append("Enter a canonical HTTPS GitHub repository URL.")
        for key, label in (("live_demo_url", "Live demo URL"), ("image_url", "Project image URL")):
            if values[key] and not valid_resume_url(values[key]):
                errors.append(f"{label} must use a valid http:// or https:// URL.")
        return values, technologies, errors

    @app.get("/projects")
    @login_required
    def projects():
        student_projects = db_session.scalars(
            select(StudentProject)
            .where(StudentProject.user_id == g.user.id)
            .order_by(StudentProject.updated_at.desc(), StudentProject.id.desc())
        ).all()
        return render_template(
            "projects/index.html",
            projects=student_projects,
            technologies_by_project={project.id: project_technologies(project) for project in student_projects},
        )

    @app.route("/projects/new", methods=("GET", "POST"))
    @login_required
    @csrf_protected
    def create_project():
        if request.method == "POST":
            values, technologies, errors = submitted_project_values()
            if errors:
                for error in dict.fromkeys(errors):
                    flash(error, "error")
                return render_template("projects/form.html", project=None, values=values), 400
            project = StudentProject(
                user_id=g.user.id,
                title=values["title"],
                description=values["description"],
                technologies_json=json.dumps(technologies),
                github_url=values["github_url"],
                live_demo_url=values["live_demo_url"] or None,
                image_url=values["image_url"] or None,
            )
            db_session.add(project)
            db_session.commit()
            flash("Project added to your portfolio.", "success")
            return redirect(url_for("projects"))
        return render_template("projects/form.html", project=None, values=project_form_values())

    @app.route("/projects/<int:project_id>/edit", methods=("GET", "POST"))
    @login_required
    @csrf_protected
    def edit_project(project_id):
        project = owned_project(project_id)
        if request.method == "POST":
            values, technologies, errors = submitted_project_values()
            if errors:
                for error in dict.fromkeys(errors):
                    flash(error, "error")
                return render_template("projects/form.html", project=project, values=values), 400
            project.title = values["title"]
            project.description = values["description"]
            project.technologies_json = json.dumps(technologies)
            project.github_url = values["github_url"]
            project.live_demo_url = values["live_demo_url"] or None
            project.image_url = values["image_url"] or None
            db_session.commit()
            flash("Project updated.", "success")
            return redirect(url_for("projects"))
        return render_template("projects/form.html", project=project, values=project_form_values(project))

    @app.route("/projects/<int:project_id>/delete", methods=("GET", "POST"))
    @login_required
    @csrf_protected
    def delete_project(project_id):
        project = owned_project(project_id)
        if request.method == "POST":
            db_session.delete(project)
            db_session.commit()
            flash("Project removed from your portfolio.", "success")
            return redirect(url_for("projects"))
        return render_template("projects/delete_confirm.html", project=project)

    @app.route("/resume", methods=("GET", "POST"))
    @login_required
    @csrf_protected
    def resume_builder():
        if request.method == "POST":
            headline = request.form.get("headline", "").strip()
            phone = request.form.get("phone", "").strip()
            location = request.form.get("location", "").strip()
            professional_summary = request.form.get("professional_summary", "").strip()
            skills_value = request.form.get("skills", "").strip()
            errors = []
            for value, label, maximum in (
                (headline, "Headline", 160),
                (phone, "Phone number", 50),
                (location, "Location", 160),
                (professional_summary, "Professional summary", 2000),
                (skills_value, "Skills", 1000),
            ):
                if len(value) > maximum:
                    errors.append(f"{label} must be {maximum} characters or fewer.")

            skills = []
            if skills_value:
                for skill in skills_value.replace("\n", ",").split(","):
                    skill = skill.strip()
                    if skill and skill.casefold() not in {item.casefold() for item in skills}:
                        skills.append(skill)
                if len(skills) > 30 or any(len(skill) > 80 for skill in skills):
                    errors.append("Add up to 30 skills, with no skill longer than 80 characters.")

            entry_fields = {
                "entry_type": request.form.getlist("entry_type"),
                "entry_title": request.form.getlist("entry_title"),
                "entry_organization": request.form.getlist("entry_organization"),
                "entry_dates": request.form.getlist("entry_dates"),
                "entry_description": request.form.getlist("entry_description"),
                "entry_url": request.form.getlist("entry_url"),
            }
            lengths = {len(values) for values in entry_fields.values()}
            if len(lengths) != 1:
                errors.append("Resume entry data is incomplete. Please try again.")
            elif len(entry_fields["entry_type"]) > MAX_RESUME_ENTRIES:
                errors.append(f"Add no more than {MAX_RESUME_ENTRIES} resume entries.")

            entries = []
            if not errors:
                for values in zip(*entry_fields.values()):
                    entry_type, title, organization, date_range, description, entry_url = (value.strip() for value in values)
                    if not any((title, organization, date_range, description, entry_url)):
                        continue
                    if entry_type not in RESUME_ENTRY_TYPES:
                        errors.append("Choose a valid resume entry type.")
                        continue
                    if not title:
                        errors.append("Each resume entry needs a title.")
                    if entry_type == "link" and not entry_url:
                        errors.append("Each link entry needs a URL.")
                    if entry_url and not valid_resume_url(entry_url):
                        errors.append("Resume links must use a valid http:// or https:// URL.")
                    for value, label, maximum in (
                        (title, "Entry title", 160),
                        (organization, "Organization", 160),
                        (date_range, "Date range", 80),
                        (description, "Entry description", 2000),
                        (entry_url, "Entry URL", 500),
                    ):
                        if len(value) > maximum:
                            errors.append(f"{label} must be {maximum} characters or fewer.")
                    entries.append({
                        "entry_type": entry_type, "title": title, "organization": organization,
                        "date_range": date_range, "description": description, "url": entry_url,
                    })
                if len(entries) > MAX_RESUME_ENTRIES:
                    errors.append(f"Add no more than {MAX_RESUME_ENTRIES} resume entries.")

            if errors:
                for error in dict.fromkeys(errors):
                    flash(error, "error")
                return render_template("resume/builder.html", **resume_context()), 400

            resume = resume_for_user(g.user.id)
            if resume is None:
                resume = Resume(user_id=g.user.id)
                db_session.add(resume)
                db_session.flush()
            resume.headline = headline or None
            resume.phone = phone or None
            resume.location = location or None
            resume.professional_summary = professional_summary or None
            resume.skills_json = json.dumps(skills) if skills else None
            for entry in resume_entries_for_user(resume):
                db_session.delete(entry)
            for position, entry in enumerate(entries):
                db_session.add(ResumeEntry(resume_id=resume.id, sort_order=position, **{
                    key: value or None for key, value in entry.items()
                }))
            db_session.commit()
            flash("Your resume has been saved.", "success")
            return redirect(url_for("resume_builder"))

        return render_template("resume/builder.html", **resume_context())

    @app.get("/resume/preview")
    @login_required
    def resume_preview():
        return render_template("resume/preview.html", preview_mode=True, pdf_mode=False, **resume_context())

    @app.get("/resume/download")
    @login_required
    def download_resume():
        context = resume_context()
        if context["resume"] is None:
            flash("Save your resume before downloading a PDF.", "error")
            return redirect(url_for("resume_builder"))
        document = render_template("resume/preview.html", preview_mode=False, pdf_mode=True, **context)
        pdf = HTML(string=document).write_pdf(
            stylesheets=[CSS(filename=str(Path(app.static_folder) / "css" / "resume.css"))]
        )
        return Response(
            pdf,
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment; filename=skillbridge-resume.pdf"},
        )

    @app.route("/profile", methods=("GET", "POST"))
    @login_required
    @csrf_protected
    def profile():
        student_profile = db_session.scalar(
            select(StudentProfile).where(StudentProfile.user_id == g.user.id)
        )

        if request.method == "POST":
            education_level = request.form.get("education_level", "").strip()
            college = request.form.get("college", "").strip()
            degree = request.form.get("degree", "").strip()
            branch = request.form.get("branch", "").strip()
            graduation_year_value = request.form.get("graduation_year", "").strip()
            career_interests = request.form.get("career_interests", "").strip()
            career_goal = request.form.get("career_goal", "").strip()
            bio = request.form.get("bio", "").strip()
            errors = []
            education_levels = {"High school", "Diploma", "Undergraduate", "Postgraduate", "Other"}

            if education_level and education_level not in education_levels:
                errors.append("Choose a valid education level.")
            for value, label, maximum in (
                (college, "College or university", 160),
                (degree, "Degree", 120),
                (branch, "Branch", 120),
                (career_interests, "Career interests", 500),
                (career_goal, "Career goal", 160),
                (bio, "Bio", 600),
            ):
                if len(value) > maximum:
                    errors.append(f"{label} must be {maximum} characters or fewer.")

            graduation_year = None
            if graduation_year_value:
                try:
                    graduation_year = int(graduation_year_value)
                except ValueError:
                    errors.append("Graduation year must be a number.")
                else:
                    current_year = datetime.now().year
                    if not 1900 <= graduation_year <= current_year + 15:
                        errors.append("Enter a graduation year between 1900 and 15 years from now.")

            if errors:
                for error in errors:
                    flash(error, "error")
                return render_template("profile.html", profile=student_profile), 400

            if student_profile is None:
                student_profile = StudentProfile(user_id=g.user.id)
                db_session.add(student_profile)

            student_profile.education_level = education_level or None
            student_profile.college = college or None
            student_profile.degree = degree or None
            student_profile.branch = branch or None
            student_profile.graduation_year = graduation_year
            student_profile.career_interests = career_interests or None
            student_profile.career_goal = career_goal or None
            student_profile.bio = bio or None
            db_session.commit()
            flash("Your profile has been saved.", "success")
            return redirect(url_for("dashboard"))

        return render_template("profile.html", profile=student_profile)

    @app.post("/logout")
    @login_required
    @csrf_protected
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("home"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
