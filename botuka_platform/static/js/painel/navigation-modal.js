(() => {
  "use strict";

  const modal = document.querySelector("[data-navigation-modal]");
  const openButtons = [...document.querySelectorAll("[data-navigation-open]")];

  if (!modal || !openButtons.length) return;

  if (modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }

  const dialog = modal.querySelector('[role="dialog"]');
  const search = modal.querySelector("[data-navigation-search]");
  const clearButton = modal.querySelector("[data-navigation-clear]");
  const emptyState = modal.querySelector("[data-navigation-empty]");
  const hub = modal.querySelector("[data-navigation-hub]");
  const panels = modal.querySelector("[data-navigation-panels]");
  const groups = [...modal.querySelectorAll("[data-navigation-group]")];
  const categoryButtons = [...modal.querySelectorAll("[data-navigation-category]")];

  let previousFocus = null;
  let currentCategory = null;

  const supportsNativeDialog =
    typeof modal.showModal === "function" && typeof modal.close === "function";

  const focusableSelector = [
    'a[href]:not([hidden])',
    'button:not([disabled]):not([hidden])',
    'input:not([disabled]):not([hidden])',
    'select:not([disabled]):not([hidden])',
    '[tabindex]:not([tabindex="-1"]):not([hidden])'
  ].join(",");

  const normalize = (value) =>
    (value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();

  const showHub = () => {
    currentCategory = null;

    if (hub) hub.hidden = false;
    if (panels) panels.hidden = true;

    groups.forEach((group) => {
      group.hidden = true;
    });

    if (emptyState) emptyState.hidden = true;
  };

  const showCategory = (category) => {
    const target = modal.querySelector(
      `[data-navigation-panel="${CSS.escape(category)}"]`
    );

    if (!target) return;

    currentCategory = category;

    if (hub) hub.hidden = true;
    if (panels) panels.hidden = false;

    groups.forEach((group) => {
      group.hidden = group !== target;
    });

    if (emptyState) emptyState.hidden = true;

    const firstFocusable = target.querySelector(
      "[data-navigation-back], a[href], button:not([disabled]), select"
    );

    window.requestAnimationFrame(() => {
      firstFocusable?.focus();
    });
  };

  const filterLinks = () => {
    const query = normalize(search?.value);

    if (!query) {
      if (currentCategory) {
        showCategory(currentCategory);
      } else {
        showHub();
      }

      if (clearButton) clearButton.hidden = true;
      return;
    }

    if (hub) hub.hidden = true;
    if (panels) panels.hidden = false;

    let visibleCount = 0;

    groups.forEach((group) => {
      let groupCount = 0;

      group.querySelectorAll("[data-navigation-link]").forEach((link) => {
        const visible = normalize(link.textContent).includes(query);
        link.hidden = !visible;

        if (visible) groupCount += 1;
      });

      group.hidden = groupCount === 0;
      visibleCount += groupCount;
    });

    if (clearButton) clearButton.hidden = false;
    if (emptyState) emptyState.hidden = visibleCount !== 0;
  };

  const open = () => {
    previousFocus = document.activeElement;

    if (search) search.value = "";

    showHub();

    modal.setAttribute("aria-hidden", "false");

    if (!modal.hasAttribute("open")) {
      if (supportsNativeDialog) {
        modal.showModal();
      } else {
        modal.setAttribute("open", "");
      }
    }

    openButtons.forEach((button) => {
      button.setAttribute("aria-expanded", "true");
    });

    document.body.classList.add("navigation-modal-open");

    window.requestAnimationFrame(() => {
      if (window.matchMedia("(min-width: 768px)").matches) {
        search?.focus();
      } else {
        dialog?.focus();
      }
    });
  };

  const close = () => {
    if (modal.hasAttribute("open")) {
      if (supportsNativeDialog) {
        modal.close();
      } else {
        modal.removeAttribute("open");
      }
    }

    modal.setAttribute("aria-hidden", "true");

    openButtons.forEach((button) => {
      button.setAttribute("aria-expanded", "false");
    });

    document.body.classList.remove("navigation-modal-open");

    if (search) search.value = "";

    showHub();

    (previousFocus || openButtons[0])?.focus();
  };

  categoryButtons.forEach((button) => {
    button.addEventListener("click", () => {
      showCategory(button.dataset.navigationCategory);
    });
  });

  modal
    .querySelectorAll(
      "[data-navigation-back], [data-navigation-group-back]"
    )
    .forEach((button) => {
      button.addEventListener("click", () => {
        if (search) search.value = "";
        showHub();
        categoryButtons[0]?.focus();
      });
    });

  openButtons.forEach((button) => {
    button.addEventListener("click", open);
  });

  modal
    .querySelectorAll("[data-navigation-close]")
    .forEach((button) => {
      button.addEventListener("click", close);
    });

  modal.addEventListener("click", (event) => {
    if (event.target === modal) close();
  });

  modal.addEventListener("cancel", (event) => {
    event.preventDefault();
    close();
  });

  window.addEventListener("pagehide", () => {
    document.body.classList.remove("navigation-modal-open");
  });

  search?.addEventListener("input", filterLinks);

  clearButton?.addEventListener("click", () => {
    search.value = "";
    filterLinks();
    search.focus();
  });

  modal
    .querySelector("[data-company-menu-select]")
    ?.addEventListener("change", (event) => {
      if (!event.target.value) return;

      window.location.href = event.target.value;
    });

  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }

    if (event.key !== "Tab") return;

    const focusable = [...dialog.querySelectorAll(focusableSelector)]
      .filter((element) => element.offsetParent !== null);

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

  showHub();
})();
