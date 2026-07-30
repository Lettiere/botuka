(function () {
  "use strict";
  const config = document.querySelector("[data-product-taxonomy]");
  if (!config) return;
  const category = document.getElementById("id_categoria_taxonomia");
  const family = document.getElementById("id_familia");
  const type = document.getElementById("id_tipo_produto");
  const segment = document.getElementById("id_segmento");
  if (!category || !family || !type || !segment) return;
  const segmentGroup = segment.closest("[data-field-step]") || segment.parentElement;

  function reset(select, label) {
    select.innerHTML = "";
    select.add(new Option(label, ""));
  }
  async function load(url, parameter, value, select, label) {
    reset(select, label);
    if (!value) return {};
    const response = await fetch(`${url}?${parameter}=${encodeURIComponent(value)}`, {
      headers: {"X-Requested-With": "XMLHttpRequest"}, credentials: "same-origin"
    });
    if (!response.ok) return {};
    const data = await response.json();
    (data.results || []).forEach(item => select.add(new Option(item.nome, item.id)));
    return data;
  }
  category.addEventListener("change", async function () {
    reset(type, "Selecione a família"); reset(segment, "Não aplicável");
    if (segmentGroup) segmentGroup.hidden = true;
    await load(config.dataset.familiesUrl, "categoria", this.value, family, "Selecione a família");
  });
  family.addEventListener("change", async function () {
    reset(segment, "Não aplicável"); if (segmentGroup) segmentGroup.hidden = true;
    await load(config.dataset.typesUrl, "familia", this.value, type, "Selecione o tipo");
  });
  type.addEventListener("change", async function () {
    const data = await load(config.dataset.segmentsUrl, "tipo", this.value, segment, "Selecione o segmento");
    const allowed = Boolean(data.permite_segmento);
    if (segmentGroup) segmentGroup.hidden = !allowed;
    segment.required = allowed && Boolean(data.exige_segmento);
    if (!allowed) segment.value = "";
  });
  if (!segment.options.length || segment.options.length <= 1) {
    if (segmentGroup) segmentGroup.hidden = true;
  }
})();
