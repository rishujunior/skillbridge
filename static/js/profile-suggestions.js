document.addEventListener("DOMContentLoaded", () => {
    const degreeInput = document.querySelector("#degree");
    const branchList = document.querySelector("#branch-suggestions");
    const interestInput = document.querySelector("#career_interests");

    const branchSuggestions = {
        "B.Tech / B.E.": ["Computer Science and Engineering (CSE)", "Information Technology (IT)", "AI & Machine Learning", "Data Science", "Electronics and Communication (ECE)", "Electrical Engineering", "Mechanical Engineering", "Civil Engineering", "Chemical Engineering"],
        "B.Tech": ["Computer Science and Engineering (CSE)", "Information Technology (IT)", "AI & Machine Learning", "Data Science", "Electronics and Communication (ECE)", "Electrical Engineering", "Mechanical Engineering", "Civil Engineering", "Chemical Engineering"],
        "B.E.": ["Computer Science and Engineering (CSE)", "Information Technology (IT)", "AI & Machine Learning", "Data Science", "Electronics and Communication (ECE)", "Electrical Engineering", "Mechanical Engineering", "Civil Engineering", "Chemical Engineering"],
        "BCA": ["Computer Applications", "Software Development", "Web Development", "Data Analytics", "Mobile App Development"],
        "MCA": ["Computer Applications", "Software Development", "Web Development", "Data Analytics", "Artificial Intelligence"],
        "B.Sc.": ["Computer Science", "Mathematics", "Statistics", "Physics", "Chemistry", "Biology"],
        "M.Sc.": ["Computer Science", "Mathematics", "Statistics", "Physics", "Chemistry", "Biology"],
        "BBA": ["Finance", "Marketing", "Human Resources", "Business Analytics", "Operations", "Management"],
        "MBA": ["Finance", "Marketing", "Human Resources", "Business Analytics", "Operations", "Management"],
        "B.Com.": ["Accounting", "Finance", "Taxation", "Commerce", "Business Analytics"],
        "M.Com.": ["Accounting", "Finance", "Taxation", "Commerce", "Business Analytics"],
        "BA": ["English", "Economics", "Psychology", "Political Science", "History", "Sociology"],
        "MA": ["English", "Economics", "Psychology", "Political Science", "History", "Sociology"],
        "Diploma": ["Computer Engineering", "Information Technology", "Mechanical Engineering", "Electrical Engineering", "Civil Engineering", "Business Management"],
    };

    const updateBranchSuggestions = () => {
        if (!degreeInput || !branchList) return;
        const suggestions = branchSuggestions[degreeInput.value.trim()] || [];
        branchList.replaceChildren(...suggestions.map((suggestion) => {
            const option = document.createElement("option");
            option.value = suggestion;
            return option;
        }));
    };

    degreeInput?.addEventListener("input", updateBranchSuggestions);
    updateBranchSuggestions();

    document.querySelectorAll("[data-interest]").forEach((chip) => {
        chip.addEventListener("click", () => {
            if (!interestInput) return;
            const interest = chip.dataset.interest;
            const current = interestInput.value.split(",").map((value) => value.trim()).filter(Boolean);
            if (!current.some((value) => value.toLowerCase() === interest.toLowerCase())) {
                current.push(interest);
                interestInput.value = current.join(", ");
                interestInput.dispatchEvent(new Event("input", { bubbles: true }));
            }
            interestInput.focus();
        });
    });
});
