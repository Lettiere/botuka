(function () {
  "use strict";
  const form = document.querySelector("[data-taxonomy-management]");
  if (!form || !window.jQuery?.fn?.select2) return;
  const fields = [
    ["#id_setor", form.dataset.sectorsUrl, "Busque o setor"],
    ["#id_categoria", form.dataset.categoriesUrl, "Busque a categoria"],
    ["#id_familia", form.dataset.familiesUrl, "Busque a família"],
  ];
  fields.forEach(([selector, url, placeholder]) => {
    const element = form.querySelector(selector);
    if (!element) return;
    window.jQuery(element).select2({
      width: "100%", allowClear: true, placeholder,
      language: {noResults: () => "Nenhum resultado", searching: () => "Buscando…", loadingMore: () => "Carregando…"},
      ajax: {
        url, dataType: "json", delay: 300, cache: true,
        data: params => ({q: params.term || "", page: params.page || 1}),
        processResults: payload => ({results: payload.results || [], pagination: payload.pagination || {more: false}}),
      },
    });
  });
}());
