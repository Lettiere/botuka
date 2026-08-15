document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-progress]").forEach((element) => {
    const value = Math.max(0, Math.min(100, Number(element.dataset.progress) || 0));
    element.style.width = value + "%";
  });
});
