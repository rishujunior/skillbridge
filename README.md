# SkillBridge

Student skill assessment and career-direction application built with Flask, SQLite, and SQLAlchemy.

## Setup

Use the existing Python 3.13.9 virtual environment:

```bash
cd /home/edith/skillbridge
./.venv/bin/pip install -r requirements.txt
```

For local development, SkillBridge generates a temporary secret key at startup and stores its SQLite database at `instance/skillbridge.sqlite3`.

For production, set a persistent secret key before starting the app:

```bash
export SKILLBRIDGE_ENV=production
export SKILLBRIDGE_SECRET_KEY="a-long-random-secret"
```

`SKILLBRIDGE_SECRET_KEY` is never committed. See `.env.example` for the supported environment variables.

## Run

```bash
cd /home/edith/skillbridge
./.venv/bin/flask --app app run --debug
```

Open `http://127.0.0.1:5000`.

## Test

```bash
cd /home/edith/skillbridge
./.venv/bin/python -m pytest
```

## Authentication routes

- `GET` / `POST` `/register`
- `GET` / `POST` `/login`
- `GET` `/dashboard` (requires login)
- `GET` / `POST` `/profile` (requires login)
- `POST` `/logout` (requires login and CSRF token)
- `POST` `/assessment/start` (requires login and CSRF token)
- `GET` / `POST` `/assessment/<attempt_id>/question/<position>` (requires login; POST requires CSRF token)
- `GET` `/assessment/<attempt_id>/results` (requires login)
- `GET` `/careers` (requires login)
- `GET` `/roadmaps` and `/roadmaps/<career_id>` (require login)
- `POST` `/roadmaps/<career_id>/milestones/<milestone_id>/progress` (requires login and CSRF token)

## Student profile database update

On startup, SQLAlchemy creates `student_profiles`, `assessment_attempts`, and `assessment_answers` when they do not exist. These are additive tables: existing `users`, profiles, and database records are not changed or deleted. No manual migration is required for this milestone.

## Skill assessment

Authenticated students can start an assessment, leave, and resume their latest in-progress attempt. The assessment contains 12 objective questions (three each for programming fundamentals, logical reasoning, problem-solving, and analytical thinking) plus three career-interest questions.

Each objective category score is the number of correct answers out of three, rounded to a whole percentage. The overall score is correct objective answers out of 12. Interest answers are saved and shown back to the student, but never contribute to knowledge or reasoning scores. Results are an initial self-evaluation, not a validated psychometric or professional aptitude test.

## Career recommendations

Career matches are calculated on request from the signed-in student's latest completed assessment and are not stored separately. Each supported path uses documented, path-specific weights across the four objective assessment categories. Its match score is 80% weighted objective fit plus 20% alignment with the three self-reported interest answers. Interest alignment is a preference signal, not evidence of ability. Profile goals and interests are displayed as context only and do not change match percentages. A match is an alignment with these rules, not a probability of career success.

## Learning roadmaps and progress

Students can choose a roadmap for any available career match. Each roadmap has Beginner, Intermediate, and Advanced milestones with practical completion tasks, prerequisites, and linked resources. Progress is stored in `roadmap_progress` per user, career ID, and milestone ID. Valid statuses are `not_started`, `in_progress`, and `completed`; only completed milestones count toward the displayed overall and stage percentages. SQLAlchemy creates this additive table on startup without modifying existing users, profiles, attempts, answers, or recommendation data.
