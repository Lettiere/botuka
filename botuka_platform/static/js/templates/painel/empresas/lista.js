document.addEventListener("DOMContentLoaded", function () {
    const filters = document.getElementById("empresasFilters");
    const toggle = document.querySelector("[data-empresas-filter-toggle]");

    if (!filters || !toggle) {
      return;
    }

    toggle.addEventListener("click", function () {
      const isOpen = filters.classList.toggle("is-open");
      toggle.innerHTML = isOpen
        ? '<i class="bi bi-x-lg"></i> Ocultar filtros'
        : '<i class="bi bi-sliders"></i> Mostrar filtros';
    });
  });
