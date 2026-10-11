document.addEventListener("DOMContentLoaded", () => {
    const list = document.querySelector("[data-resume-entry-list]");
    const template = document.querySelector("#resume-entry-template");
    const addButton = document.querySelector("[data-add-resume-entry]");
    if (!list || !template || !addButton) return;

    const updateNumbers = () => {
        list.querySelectorAll("[data-resume-entry]").forEach((entry, index) => {
            entry.querySelector(".resume-entry-card__number").textContent = index + 1;
            entry.querySelector("[data-remove-resume-entry]").setAttribute("aria-label", `Remove resume entry ${index + 1}`);
        });
    };
    addButton.addEventListener("click", () => {
        list.append(template.content.cloneNode(true));
        updateNumbers();
        list.querySelector("[data-resume-entry]:last-child select").focus();
    });
    list.addEventListener("click", (event) => {
        const remove = event.target.closest("[data-remove-resume-entry]");
        if (!remove) return;
        remove.closest("[data-resume-entry]").remove();
        updateNumbers();
    });
    updateNumbers();
});
