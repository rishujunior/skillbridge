"""Question definitions and deterministic scoring for the SkillBridge assessment."""

from collections import defaultdict


OBJECTIVE_CATEGORIES = (
    "programming",
    "logical_reasoning",
    "problem_solving",
    "analytical_thinking",
)

CATEGORY_LABELS = {
    "programming": "Programming fundamentals",
    "logical_reasoning": "Logical reasoning",
    "problem_solving": "Problem-solving",
    "analytical_thinking": "Analytical thinking",
}

# Preference questions intentionally have no correct answer and never contribute
# to the objective category scores.
QUESTIONS = (
    {
        "id": "programming_variables", "category": "programming",
        "prompt": "After `count = 3` and then `count = count + 2`, what is `count`?",
        "options": (("a", "3"), ("b", "5"), ("c", "32"), ("d", "An error occurs")), "correct": "b",
    },
    {
        "id": "programming_condition", "category": "programming",
        "prompt": "Which condition checks whether `score` is at least 60?",
        "options": (("a", "score = 60"), ("b", "score > 60"), ("c", "score >= 60"), ("d", "score <= 60")), "correct": "c",
    },
    {
        "id": "programming_function", "category": "programming",
        "prompt": "What is a main benefit of putting repeated instructions in a function?",
        "options": (("a", "It makes a program use no memory"), ("b", "It lets the instructions be reused"), ("c", "It removes the need to test code"), ("d", "It automatically fixes errors")), "correct": "b",
    },
    {
        "id": "logic_sequence", "category": "logical_reasoning",
        "prompt": "What number comes next: 2, 6, 12, 20, __?",
        "options": (("a", "24"), ("b", "28"), ("c", "30"), ("d", "32")), "correct": "c",
    },
    {
        "id": "logic_deduction", "category": "logical_reasoning",
        "prompt": "All data analysts work with data. Mira works with data. What can be concluded?",
        "options": (("a", "Mira is definitely a data analyst"), ("b", "Mira is not a data analyst"), ("c", "Mira may be a data analyst, but it is not certain"), ("d", "No conclusion can be made about data analysts")), "correct": "c",
    },
    {
        "id": "logic_conditions", "category": "logical_reasoning",
        "prompt": "A task is approved only when both review A and review B pass. Review A passed, B did not. Is it approved?",
        "options": (("a", "Yes, because one review passed"), ("b", "No, because both must pass"), ("c", "Yes, if the task is urgent"), ("d", "There is not enough information")), "correct": "b",
    },
    {
        "id": "problem_debugging", "category": "problem_solving",
        "prompt": "A program gives an unexpected result. What is the most useful first step?",
        "options": (("a", "Change many parts at once"), ("b", "Reproduce the issue and inspect the inputs and output"), ("c", "Assume the computer is wrong"), ("d", "Delete the feature")), "correct": "b",
    },
    {
        "id": "problem_decomposition", "category": "problem_solving",
        "prompt": "When tackling a large unfamiliar task, which approach is usually most effective?",
        "options": (("a", "Break it into smaller testable parts"), ("b", "Wait until every detail is known"), ("c", "Start with the hardest part without a plan"), ("d", "Avoid writing down assumptions")), "correct": "a",
    },
    {
        "id": "problem_testing", "category": "problem_solving",
        "prompt": "Why test an edge case such as an empty list?",
        "options": (("a", "It makes ordinary cases unnecessary"), ("b", "It can reveal behavior that typical inputs miss"), ("c", "It guarantees every future bug is fixed"), ("d", "It only matters for visual design")), "correct": "b",
    },
    {
        "id": "analysis_percentage", "category": "analytical_thinking",
        "prompt": "A group grows from 80 students to 100 students. What is the percentage increase?",
        "options": (("a", "20%"), ("b", "25%"), ("c", "80%"), ("d", "125%")), "correct": "b",
    },
    {
        "id": "analysis_trend", "category": "analytical_thinking",
        "prompt": "Monthly sign-ups are 40, 45, 50, and 55. Which statement is supported by the data?",
        "options": (("a", "Sign-ups increase by 5 each month"), ("b", "Sign-ups double each month"), ("c", "Sign-ups are falling"), ("d", "Next month must be 60")), "correct": "a",
    },
    {
        "id": "analysis_data", "category": "analytical_thinking",
        "prompt": "Which comparison best helps decide which of two study methods has a higher average score?",
        "options": (("a", "Compare the average scores from equally measured groups"), ("b", "Compare the largest single score only"), ("c", "Use whichever method has the longer name"), ("d", "Ignore the scores")), "correct": "a",
    },
    {
        "id": "interest_activity", "category": "interests",
        "prompt": "Which kind of work activity interests you most right now?",
        "options": (("a", "Building or improving software"), ("b", "Investigating data and patterns"), ("c", "Designing solutions with people"), ("d", "Planning and coordinating work")),
    },
    {
        "id": "interest_problem", "category": "interests",
        "prompt": "Which type of problem would you most like to explore?",
        "options": (("a", "Making a process more reliable"), ("b", "Finding insights in information"), ("c", "Making an experience easier to use"), ("d", "Organizing a team effort")),
    },
    {
        "id": "interest_learning", "category": "interests",
        "prompt": "What learning activity feels most motivating to you?",
        "options": (("a", "Writing and testing code"), ("b", "Solving logic puzzles"), ("c", "Researching a real-world question"), ("d", "Collaborating on a project")),
    },
)

QUESTION_BY_ID = {question["id"]: question for question in QUESTIONS}


def calculate_scores(answers):
    """Return objective percentage scores from a {question_id: option_id} mapping."""
    totals = defaultdict(int)
    correct = defaultdict(int)
    for question in QUESTIONS:
        category = question["category"]
        if category not in OBJECTIVE_CATEGORIES:
            continue
        totals[category] += 1
        if answers.get(question["id"]) == question["correct"]:
            correct[category] += 1

    scores = {
        category: round(correct[category] / totals[category] * 100)
        for category in OBJECTIVE_CATEGORIES
    }
    scores["overall"] = round(sum(correct.values()) / sum(totals.values()) * 100)
    return scores


def option_label(question, value):
    return dict(question["options"]).get(value)
