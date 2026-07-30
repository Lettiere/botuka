(function () {
  "use strict";
  const wizard = document.querySelector("[data-product-wizard]");
  if (!wizard) return;
  const form = wizard.querySelector("[data-product-form]");
  const steps = [...wizard.querySelectorAll(".wizard-step")];
  const total = 7;
  let current = 1;

  function showStep(number, focus) {
    current = Math.max(1, Math.min(total, Number(number)));
    steps.forEach(step => { step.hidden = Number(step.dataset.step) !== current; });
    wizard.querySelectorAll("[data-step-target]").forEach(button => {
      button.classList.toggle("is-active", Number(button.dataset.stepTarget) === current);
      button.setAttribute("aria-current", Number(button.dataset.stepTarget) === current ? "step" : "false");
    });
    const percentage = Math.round(current / total * 100);
    wizard.querySelector("[data-progress-bar]").style.width = `${percentage}%`;
    wizard.querySelector("[data-progress-text]").textContent = `Etapa ${current} de ${total} · ${percentage}%`;
    sessionStorage.setItem("botuka-product-form-step", String(current));
    if (current === 7) updateReview();
    if (focus) steps[current - 1].querySelector("h2")?.focus();
  }
  wizard.addEventListener("click", event => {
    const target = event.target.closest("[data-step-target]");
    if (target) showStep(target.dataset.stepTarget, true);
    if (event.target.closest("[data-next]")) showStep(current + 1, true);
    if (event.target.closest("[data-previous]")) showStep(current - 1, true);
  });

  const category = form.querySelector("#id_categoria_taxonomia");
  const family = form.querySelector("#id_familia");
  const type = form.querySelector("#id_tipo_produto");
  const segment = form.querySelector("#id_segmento");
  const segmentField = segment?.closest(".field");
  function reset(select, label) {
    if (!select) return;
    select.replaceChildren(new Option(label, ""));
  }
  async function load(url, key, value, select, label) {
    reset(select, label);
    if (!value) return {};
    const status = form.querySelector(`[data-taxonomy-status="${key === "categoria" ? "familia" : key === "familia" ? "tipo" : "segmento"}"]`);
    if (status) status.textContent = "Carregando opções…";
    select.disabled = true;
    try {
      const response = await fetch(`${url}?${key}=${encodeURIComponent(value)}`, {
        credentials: "same-origin", headers: {"X-Requested-With": "XMLHttpRequest"}
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Não foi possível carregar os dados.");
      (payload.results || []).forEach(item => select.add(new Option(item.nome, item.id)));
      if (status) status.textContent = payload.results?.length ? "" : (
        key === "categoria" ? "Esta categoria ainda não possui famílias cadastradas."
        : key === "familia" ? "Esta família ainda não possui tipos de produto cadastrados."
        : "Nenhum segmento foi configurado para este tipo."
      );
      return payload;
    } catch (error) {
      if (status) status.textContent = `${error.message} Altere a seleção para tentar novamente.`;
      return {};
    } finally {
      select.disabled = false;
    }
  }
  category?.addEventListener("change", async () => {
    reset(type, "Selecione primeiro a família"); reset(segment, "Não aplicável");
    if (segmentField) segmentField.hidden = true;
    await load(wizard.dataset.familiesUrl, "categoria", category.value, family, "Selecione a família");
  });
  family?.addEventListener("change", async () => {
    reset(segment, "Não aplicável"); if (segmentField) segmentField.hidden = true;
    await load(wizard.dataset.typesUrl, "familia", family.value, type, "Selecione o tipo");
  });
  type?.addEventListener("change", async () => {
    const data = await load(wizard.dataset.segmentsUrl, "tipo", type.value, segment, "Selecione o segmento");
    const allowed = Boolean(data.permite_segmento);
    if (segmentField) segmentField.hidden = !allowed;
    segment.required = allowed && Boolean(data.exige_segmento);
    if (!allowed) segment.value = "";
  });
  if (segmentField && !segment?.value && segment?.options.length <= 1) segmentField.hidden = true;

  function youtubeId(value) {
    try {
      const url = new URL(value);
      const host = url.hostname.replace(/^www\./, "");
      if (host === "youtu.be") return url.pathname.split("/")[1] || "";
      if (!["youtube.com", "m.youtube.com"].includes(host)) return "";
      if (url.pathname === "/watch") return url.searchParams.get("v") || "";
      const match = url.pathname.match(/^\/(?:embed|shorts|live)\/([^/]+)/);
      return match ? match[1] : "";
    } catch (_) { return ""; }
  }
  function updateVideoRow(row) {
    const input = row.querySelector("[data-video-url]");
    const caption = row.querySelector("[data-video-caption]")?.value || "";
    const preview = row.querySelector("[data-video-preview]");
    if (!input || !preview) return;
    const id = youtubeId(input.value);
    preview.replaceChildren();
    if (!input.value) return;
    if (!id) { preview.textContent = "Link do YouTube inválido."; preview.classList.add("is-invalid"); return; }
    preview.classList.remove("is-invalid");
    const iframe = document.createElement("iframe");
    iframe.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(id)}`;
    iframe.loading = "lazy"; iframe.title = caption || "Prévia do vídeo"; iframe.allowFullscreen = true;
    preview.append(iframe);
    if (caption) { const text = document.createElement("p"); text.textContent = caption; preview.append(text); }
  }
  const videoList = form.querySelector("[data-video-list]");
  const totalForms = form.querySelector("#id_videos-TOTAL_FORMS");
  function activeVideoRows() {
    return [...videoList.querySelectorAll("[data-video-form]")].filter(row => !row.hidden);
  }
  function renumberVideos() {
    activeVideoRows().forEach((row, index) => {
      row.querySelector("[data-video-number]").textContent = String(index + 1);
      const order = row.querySelector("[data-video-order]");
      if (order && !order.value) order.value = String(index + 1);
    });
  }
  form.querySelector("[data-add-video]")?.addEventListener("click", () => {
    if (activeVideoRows().length >= 8) return;
    const index = Number(totalForms.value);
    const html = form.querySelector("[data-video-empty-form]").innerHTML.replaceAll("__prefix__", String(index));
    videoList.insertAdjacentHTML("beforeend", html);
    totalForms.value = String(index + 1);
    renumberVideos();
  });
  videoList?.addEventListener("click", event => {
    const remove = event.target.closest("[data-remove-video]");
    if (!remove) return;
    const row = remove.closest("[data-video-form]");
    const deletion = row.querySelector("input[name$='-DELETE']");
    if (deletion) deletion.checked = true;
    row.hidden = true;
    renumberVideos();
  });
  videoList?.addEventListener("input", event => {
    const row = event.target.closest("[data-video-form]");
    if (row) updateVideoRow(row);
  });
  activeVideoRows().forEach(updateVideoRow);
  renumberVideos();

  const mainImage = form.querySelector("#id_imagem_principal_upload");
  const gallery = form.querySelector("#id_galeria_upload");
  function previewFiles(input, container, multiple) {
    if (!input || !container) return;
    container.replaceChildren();
    [...input.files].slice(0, multiple ? 12 : 1).forEach(file => {
      const image = document.createElement("img");
      image.src = URL.createObjectURL(file); image.alt = file.name;
      image.onload = () => URL.revokeObjectURL(image.src);
      container.append(image);
    });
  }
  mainImage?.addEventListener("change", () => previewFiles(mainImage, form.querySelector("[data-main-image-preview]"), false));
  gallery?.addEventListener("change", () => previewFiles(gallery, form.querySelector("[data-gallery-preview]"), true));

  function valueOf(control) {
    if (control.type === "checkbox") return control.checked ? "Sim" : "Não";
    if (control.tagName === "SELECT") return control.selectedOptions[0]?.text || "Não informado";
    const temporary = document.createElement("div"); temporary.innerHTML = control.value || "";
    return temporary.textContent.trim().slice(0, 240) || "Não informado";
  }
  function updateReview() {
    for (let step = 1; step <= 5; step += 1) {
      const block = form.querySelector(`[data-review-block="${step}"]`);
      block.replaceChildren();
      form.querySelectorAll(`[data_step="${step}"]`).forEach(control => {
        if (control.type === "hidden" || control.type === "file") return;
        const dt = document.createElement("dt");
        dt.textContent = control.closest(".field")?.querySelector("label")?.textContent.trim() || control.name;
        const dd = document.createElement("dd"); dd.textContent = valueOf(control);
        block.append(dt, dd);
      });
    }
    const newImages = (mainImage?.files.length || 0) + (gallery?.files.length || 0);
    const existingImages = Number(wizard.dataset.existingImages || 0);
    form.querySelector("[data-review-images]").textContent = `${existingImages} existente(s), ${newImages} nova(s).`;
    const videos = form.querySelector("[data-review-videos]"); videos.replaceChildren();
    activeVideoRows().forEach((row, index) => {
      const text = document.createElement("p");
      const url = row.querySelector("[data-video-url]")?.value || "Sem link";
      const caption = row.querySelector("[data-video-caption]")?.value || "Sem legenda";
      text.textContent = `${index + 1}. ${caption} — ${url}${youtubeId(url) ? "" : " (inválido)"}`;
      videos.append(text);
    });
    if (!videos.children.length) videos.textContent = "Nenhum vídeo.";
  }

  form.addEventListener("submit", event => {
    if (!form.checkValidity()) {
      event.preventDefault();
      const invalid = form.querySelector(":invalid");
      const step = Number(invalid?.dataset.step || invalid?.closest(".wizard-step")?.dataset.step || 1);
      showStep(step, true); invalid?.focus(); return;
    }
    const submit = form.querySelector("[data-submit]");
    submit.disabled = true;
    form.querySelector("[data-submit-label]").hidden = true;
    form.querySelector("[data-submit-loading]").hidden = false;
  });
  const serverError = form.querySelector(".has-error");
  showStep(serverError ? Number(serverError.closest(".wizard-step")?.dataset.step || 1) : Number(sessionStorage.getItem("botuka-product-form-step") || 1));
})();
