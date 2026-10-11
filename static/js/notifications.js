document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".flash").forEach((notice) => {
        const dismiss = () => notice.remove();
        notice.querySelector(".flash-dismiss")?.addEventListener("click", dismiss);

        const delay = Number(notice.dataset.autoDismiss);
        if (delay > 0) {
            window.setTimeout(dismiss, delay);
        }
    });
});
