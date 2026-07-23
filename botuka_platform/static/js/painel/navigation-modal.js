(() => {
  "use strict";

  const modal = document.querySelector("[data-navigation-modal]");
  const openButton = document.querySelector("[data-navigation-open]");
  if (!modal || !openButton) return;

  if (modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }

  const dialog = modal.querySelector('[role="dialog"]');
  const search = modal.querySelector("[data-navigation-search]");
  const clearButton = modal.querySelector("[data-navigation-clear]");
  const emptyState = modal.querySelector("[data-navigation-empty]");
  const groups = [...modal.querySelectorAll("[data-navigation-group]")];
  let previousFocus = null;

  const focusableSelector = [
    'a[href]:not([hidden])',
    'button:not([disabled]):not([hidden])',
    'input:not([disabled]):not([hidden])',
    '[tabindex]:not([tabindex="-1"]):not([hidden])'
  ].join(",");

  const normalize = (value) =>
    value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();

  const filterLinks = () => {
    const query = normalize(search.value);
    let visibleCount = 0;

    groups.forEach((group) => {
      let groupCount = 0;
      group.querySelectorAll("[data-navigation-link]").forEach((link) => {
        const visible = !query || normalize(link.textContent).includes(query);
        link.hidden = !visible;
        if (visible) groupCount += 1;
      });
      group.hidden = groupCount === 0;
      visibleCount += groupCount;
      if (query && groupCount && window.matchMedia("(max-width: 767.98px)").matches) {
        group.querySelector("[data-navigation-group-toggle]")?.setAttribute("aria-expanded", "true");
      }
    });

    clearButton.hidden = !query;
    emptyState.hidden = visibleCount !== 0;
  };

  const open = () => {
    previousFocus = document.activeElement;
    modal.setAttribute("aria-hidden", "false");
    if (!modal.open) modal.showModal();
    openButton.setAttribute("aria-expanded", "true");
    document.body.classList.add("navigation-modal-open");
    window.requestAnimationFrame(() => search.focus());
  };

  const close = () => {
    if (modal.open) modal.close();
    modal.setAttribute("aria-hidden", "true");
    openButton.setAttribute("aria-expanded", "false");
    document.body.classList.remove("navigation-modal-open");
    search.value = "";
    filterLinks();
    (previousFocus || openButton).focus();
  };

  openButton.addEventListener("click", open);
  modal.querySelectorAll("[data-navigation-close]").forEach((button) => button.addEventListener("click", close));
  modal.addEventListener("click", (event) => {
    if (event.target === modal) close();
  });
  modal.addEventListener("cancel", (event) => {
    event.preventDefault();
    close();
  });
  search.addEventListener("input", filterLinks);
  clearButton.addEventListener("click", () => {
    search.value = "";
    filterLinks();
    search.focus();
  });

  modal.querySelectorAll("[data-navigation-group-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!window.matchMedia("(max-width: 767.98px)").matches) return;
      button.setAttribute("aria-expanded", String(button.getAttribute("aria-expanded") !== "true"));
    });
  });

  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;

    const focusable = [...dialog.querySelectorAll(focusableSelector)].filter(
      (element) => element.offsetParent !== null
    );
    if (!focusable.length) {
      event.preventDefault();
      dialog.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
})();
