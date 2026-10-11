(() => {
    const storageKey = "skillbridge-theme";
    const root = document.documentElement;
    const mediaQuery = window.matchMedia?.("(prefers-color-scheme: dark)");

    const storedTheme = () => {
        try {
            const value = window.localStorage.getItem(storageKey);
            return value === "dark" || value === "light" ? value : null;
        } catch (_error) {
            return null;
        }
    };

    const systemTheme = () => mediaQuery?.matches ? "dark" : "light";

    const updateButtons = (theme) => {
        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            const isDark = theme === "dark";
            const action = `Switch to ${isDark ? "light" : "dark"} theme`;
            button.setAttribute("aria-pressed", String(isDark));
            button.setAttribute("aria-label", action);
            button.setAttribute("title", action);
        });
    };

    const applyTheme = (theme, persist = false) => {
        root.dataset.theme = theme;
        root.style.colorScheme = theme;
        const themeColor = document.querySelector('meta[name="theme-color"]');
        if (themeColor) themeColor.content = theme === "dark" ? "#070b1d" : "#f7f8ff";
        if (persist) {
            try {
                window.localStorage.setItem(storageKey, theme);
            } catch (_error) {
                // The selected theme remains active if storage is unavailable.
            }
        }
        updateButtons(theme);
    };

    document.addEventListener("DOMContentLoaded", () => {
        applyTheme(storedTheme() || root.dataset.theme || systemTheme());
        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            button.addEventListener("click", () => {
                applyTheme(root.dataset.theme === "dark" ? "light" : "dark", true);
            });
        });
    });

    mediaQuery?.addEventListener("change", (event) => {
        if (!storedTheme()) applyTheme(event.matches ? "dark" : "light");
    });
})();
