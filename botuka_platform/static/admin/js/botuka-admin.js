(() => {
  "use strict";
  const root = document.documentElement;
  const body = document.body;
  const storage = {
    get(key) { try { return localStorage.getItem(key); } catch (_) { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (_) {} },
  };

  const applyTheme = (theme) => {
    const value = theme === "dark" ? "dark" : "light";
    root.dataset.theme = value;
    document.querySelectorAll("#botuka-theme-toggle i").forEach((icon) => {
      icon.className = value === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
    });
  };
  applyTheme(storage.get("botuka-admin-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  document.querySelectorAll("#botuka-theme-toggle").forEach((button) => button.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    storage.set("botuka-admin-theme", next);
  }));

  const collapse = document.querySelector("#botuka-sidebar-collapse");
  if (storage.get("botuka-admin-sidebar") === "collapsed") body.classList.add("sidebar-collapsed");
  collapse?.addEventListener("click", () => {
    body.classList.toggle("sidebar-collapsed");
    const expanded = !body.classList.contains("sidebar-collapsed");
    collapse.setAttribute("aria-expanded", String(expanded));
    storage.set("botuka-admin-sidebar", expanded ? "expanded" : "collapsed");
  });

  const menu = document.querySelector("#botuka-menu-toggle");
  const backdrop = document.querySelector("#botuka-sidebar-backdrop");
  const setMobileMenu = (open) => {
    body.classList.toggle("sidebar-mobile-open", open);
    menu?.setAttribute("aria-expanded", String(open));
  };
  menu?.addEventListener("click", () => setMobileMenu(!body.classList.contains("sidebar-mobile-open")));
  backdrop?.addEventListener("click", () => setMobileMenu(false));

  const filter = document.querySelector("#nav-filter");
  filter?.addEventListener("input", () => {
    const query = filter.value.trim().toLocaleLowerCase();
    document.querySelectorAll("[data-nav-label]").forEach((item) => {
      item.hidden = Boolean(query) && !item.dataset.navLabel.toLocaleLowerCase().includes(query);
    });
    document.querySelectorAll(".botuka-nav-group").forEach((group) => {
      group.hidden = !group.querySelector("li:not([hidden])");
    });
  });

  const current = location.pathname.replace(/\/$/, "");
  document.querySelectorAll("#nav-sidebar a[href]").forEach((link) => {
    const path = new URL(link.href, location.origin).pathname.replace(/\/$/, "");
    if (path && (current === path || current.startsWith(`${path}/`))) link.setAttribute("aria-current", "page");
  });

  const adminFilter = document.querySelector("#changelist-filter");
  if (adminFilter) {
    adminFilter.setAttribute("aria-hidden", "false");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button botuka-admin-filter-toggle";
    button.innerHTML = '<i class="bi bi-funnel"></i> Filtros';
    button.setAttribute("aria-controls", "changelist-filter");
    button.setAttribute("aria-expanded", "false");
    document.querySelector("#changelist")?.prepend(button);
    button.addEventListener("click", () => {
      const open = adminFilter.classList.toggle("is-open");
      button.setAttribute("aria-expanded", String(open));
      adminFilter.setAttribute("aria-hidden", String(!open));
    });
  }

  const changeForm = document.querySelector(".change-form #content-main form");
  const fieldsets = changeForm ? [...changeForm.querySelectorAll(":scope > div > fieldset.module")] : [];
  if (fieldsets.length > 1) {
    const tabs = document.createElement("div");
    tabs.className = "botuka-form-tabs";
    tabs.setAttribute("role", "tablist");
    fieldsets.forEach((fieldset, index) => {
      const id = fieldset.id || `botuka-admin-fieldset-${index}`;
      fieldset.id = id;
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "tab");
      button.setAttribute("aria-controls", id);
      button.textContent = fieldset.querySelector("h2")?.textContent.trim() || `Seção ${index + 1}`;
      button.addEventListener("click", () => {
        fieldsets.forEach((item) => item.classList.toggle("botuka-tab-hidden", item !== fieldset));
        tabs.querySelectorAll("[role=tab]").forEach((tab) => {
          const selected = tab === button;
          tab.setAttribute("aria-selected", String(selected));
          tab.tabIndex = selected ? 0 : -1;
        });
      });
      tabs.append(button);
    });
    changeForm.prepend(tabs);
    const initialIndex = Math.max(fieldsets.findIndex((fieldset) => fieldset.querySelector(".errors, .errorlist")), 0);
    tabs.children[initialIndex].click();
  }

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    setMobileMenu(false);
    adminFilter?.classList.remove("is-open");
  });
})();
