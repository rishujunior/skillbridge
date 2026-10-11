document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.querySelector("[data-sidebar-toggle]");
    const backdrop = document.querySelector("[data-sidebar-backdrop]");
    const sidebar = document.querySelector(".app-sidebar");

    if (!toggle || !backdrop || !sidebar) return;

    const closeSidebar = () => {
        document.body.classList.remove("sidebar-open");
        toggle.setAttribute("aria-expanded", "false");
        backdrop.hidden = true;
    };
    const openSidebar = () => {
        document.body.classList.add("sidebar-open");
        toggle.setAttribute("aria-expanded", "true");
        backdrop.hidden = false;
    };

    toggle.addEventListener("click", () => {
        if (document.body.classList.contains("sidebar-open")) closeSidebar();
        else openSidebar();
    });
    backdrop.addEventListener("click", closeSidebar);
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && document.body.classList.contains("sidebar-open")) {
            closeSidebar();
            toggle.focus();
        }
    });
    sidebar.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeSidebar));
});
