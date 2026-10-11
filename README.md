# SkillBridge

SkillBridge is a Flask web application that helps students record their profile, assess foundational skills, explore explainable career matches, follow learning roadmaps, and present their work through a resume and project portfolio. It uses SQLite and SQLAlchemy for local persistence.

## Features

- Account registration, login, logout, and authenticated student workspaces.
- Student profiles for education, graduation year, career interests and goals, and a short bio, with a dashboard completion indicator.
- A resumable 15-question skill assessment: 12 objective questions across programming fundamentals, logical reasoning, problem-solving, and analytical thinking, plus three self-reported interest questions.
- Deterministic career recommendations for Software Developer, Data Analyst, Cybersecurity Analyst, Game Developer, UI/UX Designer, and QA / Test Engineer.
- Career-specific learning roadmaps with Beginner, Intermediate, and Advanced milestones, prerequisites, resources, completion criteria, and per-milestone progress tracking.
- Progress analytics for the newest valid completed assessments (up to 10), category scores, change from the prior assessment, and roadmap completion.
- Resume builder with profile-prefilled details, skills, ordered project/experience/certification/link entries, preview, and PDF download.
- Private student project portfolios with create, edit, and delete flows, technology tags, a required GitHub repository URL, and optional live-demo and image URLs.
- Light and dark themes. The selected theme is stored in browser local storage; otherwise the interface follows the system color preference.

## Prerequisites

- Python 3.10 or newer
- `pip` and the standard-library `venv` module

The Python dependencies are defined in [`requirements.txt`](requirements.txt): Flask, SQLAlchemy, pytest, and WeasyPrint. PDF export uses WeasyPrint; ensure its platform requirements are available in the environment where you run the application.

## Installation

Clone the repository and create an isolated environment:

```bash
cd ~/skillbridge
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install the project dependencies:

```bash
python -m pip install -r requirements.txt
```

## Environment configuration

Use [`.env.example`](.env.example) as a reference for supported settings. The application reads environment variables directly; it does not load a `.env` file automatically.

| Variable | Required | Behavior |
| --- | --- | --- |
| `SKILLBRIDGE_SECRET_KEY` | Required when `SKILLBRIDGE_ENV=production` | Flask session secret. In non-production mode, a temporary random value is generated on each startup if this variable is absent. |
| `SKILLBRIDGE_DATABASE_URL` | No | SQLAlchemy database URL. Defaults to the SQLite database at `instance/skillbridge.sqlite3`. |
| `SKILLBRIDGE_ENV` | No | Set to `production` to require a persistent secret key and mark session cookies as secure. |

For example, export configuration in the shell before starting the application:

```bash
export SKILLBRIDGE_ENV=production
export SKILLBRIDGE_SECRET_KEY='replace-with-a-long-random-secret'
export SKILLBRIDGE_DATABASE_URL='sqlite:///instance/skillbridge.sqlite3'
```

Do not commit real secret values or local database files.

## Run locally

From the activated virtual environment, start Flask in debug mode:

```bash
cd ~/skillbridge
flask --app app run --debug
```

Flask listens on `http://127.0.0.1:5000` by default. To choose another local port, pass it explicitly:

```bash
flask --app app run --debug --port 8000
```

## Testing

Run the pytest suite from the repository root:

```bash
cd ~/skillbridge
python -m pytest
```

The test suite covers authentication, profiles, assessments, career recommendations, roadmaps and progress, dashboard and analytics behavior, resumes and PDF responses, and project-portfolio ownership and validation.

## Assessment and recommendations

### Scoring

The assessment has four objective categories with three questions each. A category score is the number correct out of three, converted to a whole percentage; the overall score is the number correct out of 12, converted to a whole percentage. The three interest questions are saved and displayed to the student, but never contribute to objective category or overall scores.

Students can resume their latest in-progress attempt. Completed attempts retain their answers and scores; results identify objective categories at or above 67% as strengths. This is an initial self-evaluation, not a validated psychometric or professional aptitude test.

### Recommendation formula

Recommendations are calculated on request from the signed-in student's latest valid completed assessment and are not stored as separate recommendation records. Each match is:

```text
round((weighted objective score × 80%) + (interest alignment × 20%))
```

Interest alignment is the percentage of the three self-reported interest answers that match the path's configured preferences. It is a preference signal, not evidence of ability. Profile interests and career goals are shown as context and do not alter match percentages. A match is an alignment with these rules, not a probability of career success.

| Career path | Objective-score weights |
| --- | --- |
| Software Developer | Programming 45%, Problem-solving 30%, Logical reasoning 15%, Analytical thinking 10% |
| Data Analyst | Analytical thinking 45%, Logical reasoning 30%, Problem-solving 15%, Programming 10% |
| Cybersecurity Analyst | Problem-solving 35%, Logical reasoning 30%, Programming 20%, Analytical thinking 15% |
| Game Developer | Programming 40%, Problem-solving 30%, Logical reasoning 20%, Analytical thinking 10% |
| UI/UX Designer | Problem-solving 35%, Analytical thinking 30%, Logical reasoning 20%, Programming 15% |
| QA / Test Engineer | Problem-solving 40%, Logical reasoning 30%, Analytical thinking 20%, Programming 10% |

For each path, categories below 70% are presented as skill gaps with a category-specific practice suggestion.

## Roadmaps and progress

Roadmaps are available only for careers returned by the current student's recommendations. Every roadmap contains Beginner, Intermediate, and Advanced stages, with milestones that include a description, practical completion criterion, prerequisites, and links to learning resources.

Milestone statuses are `not_started`, `in_progress`, and `completed`. Only `completed` milestones count toward the displayed stage and overall completion percentages. Progress is stored independently for each user, career, and milestone.

## Key routes

All routes marked “login” require an authenticated session. State-changing form submissions also require the session’s CSRF token.

| Method | Route | Access / purpose |
| --- | --- | --- |
| `GET` | `/` | Public landing page |
| `GET`, `POST` | `/register`, `/login` | Public account registration and login; `POST` requires CSRF |
| `POST` | `/logout` | Login and CSRF required |
| `GET` | `/dashboard` | Login required; profile, assessment, recommendation, and roadmap summary |
| `GET`, `POST` | `/profile` | Login required; `POST` requires CSRF |
| `GET` | `/analytics` | Login required; assessment and roadmap progress analytics |
| `POST` | `/assessment/start` | Login and CSRF required |
| `GET`, `POST` | `/assessment/<attempt_id>/question/<position>` | Login required; `POST` requires CSRF |
| `GET` | `/assessment/<attempt_id>/results` | Login required |
| `GET` | `/careers` | Login required; career matches |
| `GET` | `/roadmaps`, `/roadmaps/<career_id>` | Login required |
| `POST` | `/roadmaps/<career_id>/milestones/<milestone_id>/progress` | Login and CSRF required |
| `GET` | `/projects` | Login required; project portfolio |
| `GET`, `POST` | `/projects/new`, `/projects/<project_id>/edit`, `/projects/<project_id>/delete` | Login required; `POST` requires CSRF |
| `GET`, `POST` | `/resume` | Login required; `POST` requires CSRF |
| `GET` | `/resume/preview`, `/resume/download` | Login required; preview or PDF download |

Passwords are stored using Werkzeug password hashes. The application validates CSRF tokens for state-changing requests, uses HTTP-only session cookies, and scopes profiles, assessment attempts, roadmaps, resumes, and projects to the signed-in user. When `SKILLBRIDGE_ENV=production`, session cookies are also configured as secure and `SameSite=Lax`.

## Database notes

By default, SkillBridge uses SQLite at `instance/skillbridge.sqlite3`, relative to the application instance directory. Set `SKILLBRIDGE_DATABASE_URL` to use another SQLAlchemy-supported database URL.

On startup, SQLAlchemy `create_all()` creates missing model tables: `users`, `student_profiles`, `assessment_attempts`, `assessment_answers`, `roadmap_progress`, `resumes`, `resume_entries`, and `student_projects`. It does not perform schema migrations or alter existing tables, so schema changes require a migration strategy outside this application.
