"""Maintainable, career-specific learning-roadmap definitions and progress helpers."""

VALID_PROGRESS_STATUSES = ("not_started", "in_progress", "completed")


def resource(title, url):
    return {"title": title, "url": url}


def milestone(identifier, topic, description, criterion, resources, prerequisites=()):
    return {
        "id": identifier,
        "topic": topic,
        "description": description,
        "criterion": criterion,
        "resources": resources,
        "prerequisites": prerequisites,
    }


PYTHON_TUTORIAL = resource("The Python Tutorial", "https://docs.python.org/3/tutorial/")
GIT_BOOK = resource("Pro Git", "https://git-scm.com/book/en/v2")
SQLBOLT = resource("SQLBolt", "https://sqlbolt.com/")
PANDAS = resource("pandas: Getting started", "https://pandas.pydata.org/docs/getting_started/index.html")
KAGGLE = resource("Kaggle Learn", "https://www.kaggle.com/learn")
OWASP = resource("OWASP Top 10", "https://owasp.org/www-project-top-ten/")
TRYHACKME = resource("TryHackMe: Pre Security", "https://tryhackme.com/path/outline/presecurity")
NIST_INCIDENTS = resource("NIST SP 800-61r3: Incident Response", "https://csrc.nist.gov/pubs/sp/800/61/r3/final")
GODOT = resource("Godot: Your first 2D game", "https://docs.godotengine.org/en/stable/getting_started/first_2d_game/index.html")
UNITY_LEARN = resource("Unity Learn", "https://learn.unity.com/")
WEBAIM = resource("WebAIM: Introduction to Web Accessibility", "https://webaim.org/intro/")
NNG = resource("Nielsen Norman Group: UX Research Cheat Sheet", "https://www.nngroup.com/articles/ux-research-cheat-sheet/")
FIGMA = resource("Figma Help Center: Get started", "https://help.figma.com/hc/en-us/categories/360002042553-Get-started")
MDN_TESTING = resource("MDN: Testing", "https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Testing")
PLAYWRIGHT = resource("Playwright: Installation", "https://playwright.dev/docs/intro")
TAU = resource("Test Automation University", "https://testautomationu.applitools.com/")


ROADMAPS = {
    "software-developer": {
        "career_name": "Software Developer",
        "stages": (
            {"id": "beginner", "name": "Beginner", "milestones": (
                milestone("sd-python-basics", "Programming foundations", "Learn variables, conditions, loops, functions, and basic data structures.", "Build a command-line program that accepts input and uses at least two functions.", (PYTHON_TUTORIAL,)),
                milestone("sd-version-control", "Version control", "Learn to track changes and collaborate safely with Git.", "Create a repository with three meaningful commits and a README.", (GIT_BOOK,), ("Programming foundations",)),
            )},
            {"id": "intermediate", "name": "Intermediate", "milestones": (
                milestone("sd-debugging", "Debugging and tests", "Practice isolating defects and checking expected behavior.", "Write tests for a small feature, reproduce one defect, and document its fix.", (MDN_TESTING,), ("Programming foundations",)),
                milestone("sd-web-project", "Build a small web project", "Connect routes, templates, and persistent data in a focused application.", "Ship a small CRUD feature with validation and an accessible interface.", (resource("Flask Tutorial", "https://flask.palletsprojects.com/en/stable/tutorial/"),), ("Version control", "Debugging and tests")),
            )},
            {"id": "advanced", "name": "Advanced", "milestones": (
                milestone("sd-design", "Design maintainable software", "Practice separating responsibilities and documenting trade-offs.", "Refactor one project into clear modules and explain the design in its README.", (GIT_BOOK,), ("Build a small web project",)),
                milestone("sd-collaboration", "Collaborative delivery", "Use issues, reviews, and release notes to deliver a change with others.", "Open a reviewed pull request or complete a documented peer review.", (GIT_BOOK,), ("Design maintainable software",)),
            )},
        ),
    },
    "data-analyst": {
        "career_name": "Data Analyst",
        "stages": (
            {"id": "beginner", "name": "Beginner", "milestones": (
                milestone("da-sql-basics", "Query structured data", "Learn SELECT, filtering, grouping, and joins.", "Solve the SQLBolt lessons through joins and save three example queries.", (SQLBOLT,)),
                milestone("da-data-literacy", "Data literacy", "Learn averages, proportions, and how to distinguish a claim from evidence.", "Write a short summary of a small dataset using two calculated measures.", (KAGGLE,)),
            )},
            {"id": "intermediate", "name": "Intermediate", "milestones": (
                milestone("da-cleaning", "Clean and explore data", "Use a notebook to inspect missing values, types, and simple patterns.", "Clean a public dataset and document three data-quality decisions.", (PANDAS,), ("Data literacy",)),
                milestone("da-visuals", "Communicate with visuals", "Choose charts that answer a specific question without misleading readers.", "Create three labelled charts and a one-page insight summary.", (KAGGLE,), ("Clean and explore data",)),
            )},
            {"id": "advanced", "name": "Advanced", "milestones": (
                milestone("da-case-study", "Complete an analysis case study", "Frame a question, analyse evidence, and communicate limits.", "Publish a reproducible analysis with data source, method, findings, and caveats.", (PANDAS,), ("Communicate with visuals",)),
                milestone("da-review", "Review analytical work", "Check assumptions, calculations, and whether conclusions follow from the data.", "Peer-review an analysis or add a documented self-review checklist to one.", (KAGGLE,), ("Complete an analysis case study",)),
            )},
        ),
    },
    "cybersecurity-analyst": {
        "career_name": "Cybersecurity Analyst",
        "stages": (
            {"id": "beginner", "name": "Beginner", "milestones": (
                milestone("cs-security-basics", "Security fundamentals", "Learn common security risks and the purpose of basic controls.", "Summarise five OWASP Top 10 risks in your own words.", (OWASP,)),
                milestone("cs-network-basics", "Networking foundations", "Learn IP addresses, ports, protocols, and common network services.", "Diagram a simple client, server, and router interaction with labelled ports.", (TRYHACKME,)),
            )},
            {"id": "intermediate", "name": "Intermediate", "milestones": (
                milestone("cs-safe-labs", "Safe hands-on practice", "Use legal training environments to investigate basic system and web risks.", "Complete a beginner security training room and record your defensive takeaways.", (TRYHACKME,), ("Security fundamentals", "Networking foundations")),
                milestone("cs-log-analysis", "Investigate logs", "Learn to recognise normal and unusual events in a small log sample.", "Write an incident note identifying a suspicious event and the evidence supporting it.", (NIST_INCIDENTS,), ("Safe hands-on practice",)),
            )},
            {"id": "advanced", "name": "Advanced", "milestones": (
                milestone("cs-response", "Incident response workflow", "Understand preparation, detection, containment, and recovery activities.", "Create a tabletop response checklist for a simulated account compromise.", (NIST_INCIDENTS,), ("Investigate logs",)),
                milestone("cs-risk-report", "Communicate security risk", "Explain risk and recommended controls clearly to a non-specialist.", "Produce a one-page risk report with evidence, impact, and prioritized mitigations.", (OWASP,), ("Incident response workflow",)),
            )},
        ),
    },
    "game-developer": {
        "career_name": "Game Developer",
        "stages": (
            {"id": "beginner", "name": "Beginner", "milestones": (
                milestone("gd-programming", "Programming for interaction", "Learn variables, functions, input, and game-loop thinking.", "Make a small interactive prototype with movement and one rule.", (PYTHON_TUTORIAL,)),
                milestone("gd-engine", "Learn a game engine", "Use scenes, nodes or objects, and assets in an engine.", "Finish the Godot first 2D game tutorial and personalise one mechanic.", (GODOT,)),
            )},
            {"id": "intermediate", "name": "Intermediate", "milestones": (
                milestone("gd-mechanics", "Design and test mechanics", "Create clear player goals, feedback, and difficulty changes.", "Prototype one mechanic and collect feedback from two players.", (UNITY_LEARN,), ("Learn a game engine",)),
                milestone("gd-debug", "Debug a playable build", "Practice finding reproducible gameplay and technical issues.", "Maintain a bug list and resolve three issues in a playable prototype.", (GODOT,), ("Design and test mechanics",)),
            )},
            {"id": "advanced", "name": "Advanced", "milestones": (
                milestone("gd-vertical-slice", "Create a vertical slice", "Build a polished small section that represents a larger game concept.", "Publish a short playable slice with instructions and credits.", (UNITY_LEARN,), ("Debug a playable build",)),
                milestone("gd-collaborate", "Collaborate on a game", "Plan scope, integrate assets, and manage changes with a team.", "Complete a shared milestone using version control and a task board.", (GIT_BOOK,), ("Create a vertical slice",)),
            )},
        ),
    },
    "ui-ux-designer": {
        "career_name": "UI/UX Designer",
        "stages": (
            {"id": "beginner", "name": "Beginner", "milestones": (
                milestone("ux-research", "User-centred research", "Learn how questions, observation, and synthesis reveal user needs.", "Conduct two short practice interviews and group the findings into themes.", (NNG,)),
                milestone("ux-accessibility", "Accessible design basics", "Learn how contrast, structure, keyboard access, and text alternatives affect users.", "Audit one screen against five accessibility considerations and list fixes.", (WEBAIM,)),
            )},
            {"id": "intermediate", "name": "Intermediate", "milestones": (
                milestone("ux-wireframes", "Wireframe a user flow", "Turn a user goal into a clear sequence of low-fidelity screens.", "Create and annotate a five-screen flow for one user task.", (FIGMA,), ("User-centred research",)),
                milestone("ux-prototype", "Prototype and test", "Build a clickable prototype and observe where people struggle.", "Test a prototype with two people and make three evidence-based revisions.", (FIGMA,), ("Wireframe a user flow", "Accessible design basics")),
            )},
            {"id": "advanced", "name": "Advanced", "milestones": (
                milestone("ux-case-study", "Document a case study", "Explain the problem, evidence, design choices, and limitations.", "Publish a concise case study with research evidence and before/after screens.", (NNG,), ("Prototype and test",)),
                milestone("ux-design-system", "Use a small design system", "Create reusable components and rules that make interfaces consistent.", "Build a component set with states, usage notes, and accessibility checks.", (FIGMA,), ("Document a case study",)),
            )},
        ),
    },
    "qa-test-engineer": {
        "career_name": "QA / Test Engineer",
        "stages": (
            {"id": "beginner", "name": "Beginner", "milestones": (
                milestone("qa-test-thinking", "Test-thinking foundations", "Learn test cases, expected results, boundaries, and defect reports.", "Write ten test cases for a familiar login or form flow.", (MDN_TESTING,)),
                milestone("qa-bug-reports", "Write useful bug reports", "Describe reproducible steps, observed behaviour, expected behaviour, and impact.", "File three practice bug reports with clear reproduction steps.", (TAU,)),
            )},
            {"id": "intermediate", "name": "Intermediate", "milestones": (
                milestone("qa-browser-tests", "Automate a browser check", "Learn the structure of a reliable end-to-end test.", "Automate one critical user flow and run it locally.", (PLAYWRIGHT,), ("Test-thinking foundations",)),
                milestone("qa-test-data", "Plan test data and edge cases", "Choose data that exercises normal, boundary, and invalid scenarios.", "Create a test-data matrix with at least eight meaningful cases.", (MDN_TESTING,), ("Write useful bug reports",)),
            )},
            {"id": "advanced", "name": "Advanced", "milestones": (
                milestone("qa-suite", "Build a maintainable test suite", "Organise checks, fixtures, and reporting so tests remain useful over time.", "Create a small suite with setup guidance and readable failure output.", (PLAYWRIGHT,), ("Automate a browser check", "Plan test data and edge cases")),
                milestone("qa-quality-strategy", "Contribute to a quality strategy", "Balance exploratory testing, automation, risk, and release evidence.", "Write a release-test plan that prioritises risks and explains coverage limits.", (TAU,), ("Build a maintainable test suite",)),
            )},
        ),
    },
}


def roadmap_for(career_id):
    return ROADMAPS.get(career_id)


def milestones_for(roadmap):
    return tuple(milestone_item for stage in roadmap["stages"] for milestone_item in stage["milestones"])


def progress_summary(roadmap, statuses):
    """Calculate completion from persisted statuses; only completed is complete."""
    stage_summaries = []
    completed_total = 0
    milestone_total = 0
    for stage in roadmap["stages"]:
        milestones = stage["milestones"]
        completed = sum(statuses.get(item["id"]) == "completed" for item in milestones)
        total = len(milestones)
        completed_total += completed
        milestone_total += total
        stage_summaries.append({
            "id": stage["id"], "name": stage["name"], "completed": completed, "total": total,
            "percentage": round(completed / total * 100) if total else 0,
            "milestones": milestones,
        })
    return {
        "completed": completed_total,
        "total": milestone_total,
        "percentage": round(completed_total / milestone_total * 100) if milestone_total else 0,
        "stages": stage_summaries,
    }
