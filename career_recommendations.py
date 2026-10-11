"""Deterministic, explainable career matching for completed SkillBridge assessments.

Match scores are alignment with these published rules, not probabilities of career
success. Objective assessment results contribute 80%; self-reported interests
contribute 20% and are never presented as evidence of technical ability.
"""

from assessment import CATEGORY_LABELS, OBJECTIVE_CATEGORIES


OBJECTIVE_FIT_WEIGHT = 0.80
INTEREST_ALIGNMENT_WEIGHT = 0.20
SKILL_GAP_THRESHOLD = 70

CATEGORY_SUGGESTIONS = {
    "programming": "Practice variables, conditions, functions, and small programs.",
    "logical_reasoning": "Practice structured logic, constraints, and step-by-step deductions.",
    "problem_solving": "Break unfamiliar problems into testable steps and review edge cases.",
    "analytical_thinking": "Practice reading trends, comparing evidence, and checking calculations.",
}

# `skill_weights` must add to 1. `interest_matches` maps each self-report
# question to answer choices considered relevant to a path. These mappings
# affect only the 20% preference-alignment portion of a match.
CAREER_PATHS = (
    {
        "id": "software-developer",
        "name": "Software Developer",
        "description": "Builds and improves software applications, features, and services.",
        "skill_weights": {"programming": 0.45, "problem_solving": 0.30, "logical_reasoning": 0.15, "analytical_thinking": 0.10},
        "interest_matches": {"interest_activity": ("a",), "interest_problem": ("a",), "interest_learning": ("a",)},
        "core_skills": ("Programming fundamentals", "Debugging", "Version control", "Collaborative development"),
    },
    {
        "id": "data-analyst",
        "name": "Data Analyst",
        "description": "Uses data to answer questions, find patterns, and communicate useful insights.",
        "skill_weights": {"analytical_thinking": 0.45, "logical_reasoning": 0.30, "problem_solving": 0.15, "programming": 0.10},
        "interest_matches": {"interest_activity": ("b",), "interest_problem": ("b",), "interest_learning": ("c",)},
        "core_skills": ("Data interpretation", "Spreadsheets or SQL", "Data visualisation", "Clear communication"),
    },
    {
        "id": "cybersecurity-analyst",
        "name": "Cybersecurity Analyst",
        "description": "Helps identify, investigate, and reduce risks to systems and information.",
        "skill_weights": {"problem_solving": 0.35, "logical_reasoning": 0.30, "programming": 0.20, "analytical_thinking": 0.15},
        "interest_matches": {"interest_activity": ("a",), "interest_problem": ("a",), "interest_learning": ("b",)},
        "core_skills": ("Security fundamentals", "Network concepts", "Incident investigation", "Risk awareness"),
    },
    {
        "id": "game-developer",
        "name": "Game Developer",
        "description": "Creates interactive game systems, mechanics, and player experiences.",
        "skill_weights": {"programming": 0.40, "problem_solving": 0.30, "logical_reasoning": 0.20, "analytical_thinking": 0.10},
        "interest_matches": {"interest_activity": ("a",), "interest_problem": ("c",), "interest_learning": ("a",)},
        "core_skills": ("Programming", "Game engines", "Debugging", "Interactive design"),
    },
    {
        "id": "ui-ux-designer",
        "name": "UI/UX Designer",
        "description": "Researches, designs, and improves digital experiences for people.",
        "skill_weights": {"problem_solving": 0.35, "analytical_thinking": 0.30, "logical_reasoning": 0.20, "programming": 0.15},
        "interest_matches": {"interest_activity": ("c",), "interest_problem": ("c",), "interest_learning": ("d",)},
        "core_skills": ("User research", "Interaction design", "Prototyping", "Usability testing"),
    },
    {
        "id": "qa-test-engineer",
        "name": "QA / Test Engineer",
        "description": "Tests software systematically to help teams deliver reliable experiences.",
        "skill_weights": {"problem_solving": 0.40, "logical_reasoning": 0.30, "analytical_thinking": 0.20, "programming": 0.10},
        "interest_matches": {"interest_activity": ("a",), "interest_problem": ("a",), "interest_learning": ("a", "b")},
        "core_skills": ("Test design", "Bug reporting", "Edge-case thinking", "Test automation"),
    },
)


def _validate_scores(scores):
    if not isinstance(scores, dict):
        raise ValueError("Assessment scores are unavailable.")
    for category in OBJECTIVE_CATEGORIES:
        score = scores.get(category)
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
            raise ValueError(f"Assessment score for {category} is invalid.")


def _skill_gaps(skill_weights, scores):
    gaps = []
    for category in skill_weights:
        score = scores[category]
        if score < SKILL_GAP_THRESHOLD:
            gaps.append({
                "category": category,
                "label": CATEGORY_LABELS[category],
                "score": score,
                "gap": SKILL_GAP_THRESHOLD - score,
                "suggestion": CATEGORY_SUGGESTIONS[category],
            })
    return gaps


def build_recommendations(scores, answers):
    """Rank paths from valid score and answer mappings without persisting data."""
    _validate_scores(scores)
    if not isinstance(answers, dict):
        raise ValueError("Assessment answers are unavailable.")

    recommendations = []
    for path in CAREER_PATHS:
        skill_fit = sum(scores[category] * weight for category, weight in path["skill_weights"].items())
        interest_matches = sum(
            answers.get(question_id) in choices
            for question_id, choices in path["interest_matches"].items()
        )
        interest_total = len(path["interest_matches"])
        interest_fit = interest_matches / interest_total * 100
        match_score = round(
            skill_fit * OBJECTIVE_FIT_WEIGHT + interest_fit * INTEREST_ALIGNMENT_WEIGHT
        )
        strengths = [
            {"label": CATEGORY_LABELS[category], "score": scores[category]}
            for category in path["skill_weights"] if scores[category] >= SKILL_GAP_THRESHOLD
        ]
        reasons = [
            f"{item['label']} scored {item['score']}% in your objective assessment."
            for item in strengths
        ]
        if interest_matches:
            reasons.append(
                f"{interest_matches} of {interest_total} self-reported interest responses align with this path."
            )
        else:
            reasons.append("None of the saved interest responses align with this path's configured preferences.")
        recommendations.append({
            "id": path["id"],
            "name": path["name"],
            "description": path["description"],
            "match_score": match_score,
            "objective_fit": round(skill_fit),
            "interest_fit": round(interest_fit),
            "interest_matches": interest_matches,
            "interest_total": interest_total,
            "skill_weights": tuple(
                {"label": CATEGORY_LABELS[category], "percentage": round(weight * 100)}
                for category, weight in path["skill_weights"].items()
            ),
            "strengths": strengths,
            "skill_gaps": _skill_gaps(path["skill_weights"], scores),
            "core_skills": path["core_skills"],
        })
    return sorted(recommendations, key=lambda recommendation: (-recommendation["match_score"], recommendation["name"]))
