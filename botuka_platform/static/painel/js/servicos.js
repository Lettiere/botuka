function providerValue(field) {
  if (!field) return '';
  if (field.tagName === 'SELECT') return field.value;
  return document.querySelector('input[name="prestador_tipo"]:checked')?.value || '';
}

function updateProvider(field) {
  const value = providerValue(field);
  document.querySelectorAll('[data-provider-panel]').forEach((panel) => {
    const visible = panel.dataset.providerPanel === value;
    panel.hidden = !visible;
    panel.querySelectorAll('select, input, textarea').forEach((control) => {
      control.disabled = !visible;
    });
  });
}

function resetSelect(select, label) {
  if (!select) return;
  select.replaceChildren(new Option(label, ''));
  if (window.jQuery?.fn?.select2) window.jQuery(select).trigger('change.select2');
}

function setSelectDisabled(select, disabled) {
  if (!select) return;
  select.disabled = disabled;
  if (window.jQuery?.fn?.select2) {
    window.jQuery(select).prop('disabled', disabled).trigger('change.select2');
  }
}

const dependencyRequests = new Map();

async function loadOptions(select, url, statusElement, emptyLabel, emptyMessage) {
  dependencyRequests.get(select)?.abort();
  const controller = new AbortController();
  dependencyRequests.set(select, controller);
  resetSelect(select, 'Carregando...');
  setSelectDisabled(select, true);
  if (statusElement) {
    statusElement.textContent = 'Carregando opções...';
    statusElement.classList.remove('text-danger');
  }

  try {
    const response = await fetch(url, {
      headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível carregar as opções.');
    if (!Array.isArray(data.results)) throw new Error('Resposta inválida do servidor.');
    resetSelect(select, emptyLabel);
    data.results.forEach((item) => select.add(new Option(item.text, item.id)));
    setSelectDisabled(select, !data.results.length);
    if (statusElement) {
      statusElement.textContent = data.results.length
        ? `${data.results.length} opção(ões) disponível(is).`
        : emptyMessage;
    }
    return data.results;
  } catch (error) {
    if (error.name === 'AbortError') return [];
    resetSelect(select, 'Não foi possível carregar');
    setSelectDisabled(select, true);
    if (statusElement) {
      statusElement.textContent = error.message;
      statusElement.classList.add('text-danger');
    }
    return [];
  } finally {
    if (dependencyRequests.get(select) === controller) {
      dependencyRequests.delete(select);
    }
  }
}

function initDependentServiceSelects() {
  const form = document.querySelector('.service-form[data-areas-url]');
  if (!form) return;
  const setorSelect = document.getElementById('id_setor');
  const areaSelect = document.getElementById('id_area');
  const profissaoSelect = document.getElementById('id_profissao');
  const tipoSelect = document.getElementById('id_tipo_servico');

  const missing = [
    ['Setor', setorSelect],
    ['Área profissional', areaSelect],
    ['Profissão', profissaoSelect],
    ['Tipo de serviço', tipoSelect],
  ]
    .filter(([, element]) => !element)
    .map(([label]) => label);

  if (missing.length) {
    console.error('[Serviços] Campos da taxonomia não encontrados.', {
      formularioEncontrado: Boolean(form),
      camposAusentes: missing,
    });
    return;
  }

  const areaStatus = document.querySelector(
    '[data-dependency-status="area"]'
  );
  const profissaoStatus = document.querySelector(
    '[data-dependency-status="profissao"]'
  );
  const tipoStatus = document.querySelector(
    '[data-dependency-status="tipo_servico"]'
  );

  console.debug('[Serviços] Inicialização dos selects dependentes.', {
    setor: setorSelect.value,
    area: areaSelect.value,
    profissao: profissaoSelect.value,
    tipoServico: tipoSelect.value,
    areasUrl: form.dataset.areasUrl,
    profissoesUrl: form.dataset.profissoesUrl,
    tiposUrl: form.dataset.tiposUrl,
  });

  async function handleSetorChange() {
    const setorId = setorSelect.value;

    console.debug('[Serviços] Setor alterado.', {
      setorId,
    });

    resetSelect(areaSelect, 'Selecione primeiro o setor');
    resetSelect(profissaoSelect, 'Selecione primeiro a área');
    resetSelect(tipoSelect, 'Selecione primeiro a profissão');

    setSelectDisabled(areaSelect, true);
    setSelectDisabled(profissaoSelect, true);
    setSelectDisabled(tipoSelect, true);

    if (!setorId) {
      if (areaStatus) {
        areaStatus.textContent =
          'As opções são carregadas de acordo com o setor.';
        areaStatus.classList.remove('text-danger');
      }
      return [];
    }

    const url =
      `${form.dataset.areasUrl}?setor_id=${encodeURIComponent(setorId)}`;

    console.debug('[Serviços] Carregando áreas.', {
      setorId,
      url,
    });

    const results = await loadOptions(
      areaSelect,
      url,
      areaStatus,
      'Selecione a área profissional',
      'Nenhuma área profissional cadastrada para este setor.'
    );

    console.debug('[Serviços] Áreas recebidas.', {
      setorId,
      quantidade: results.length,
      disabled: areaSelect.disabled,
    });

    return results;
  }

  async function handleAreaChange() {
    const areaId = areaSelect.value;

    console.debug('[Serviços] Área alterada.', {
      areaId,
    });

    resetSelect(profissaoSelect, 'Selecione primeiro a área');
    resetSelect(tipoSelect, 'Selecione primeiro a profissão');

    setSelectDisabled(profissaoSelect, true);
    setSelectDisabled(tipoSelect, true);

    if (!areaId) {
      return [];
    }

    const url =
      `${form.dataset.profissoesUrl}?area_profissional_id=${encodeURIComponent(areaId)}`;

    console.debug('[Serviços] Carregando profissões.', {
      areaId,
      url,
    });

    const results = await loadOptions(
      profissaoSelect,
      url,
      profissaoStatus,
      'Selecione a profissão',
      'Nenhuma profissão cadastrada para esta área profissional.'
    );

    console.debug('[Serviços] Profissões recebidas.', {
      areaId,
      quantidade: results.length,
      disabled: profissaoSelect.disabled,
    });

    return results;
  }

  async function handleProfissaoChange() {
    const profissaoId = profissaoSelect.value;

    console.debug('[Serviços] Profissão alterada.', {
      profissaoId,
    });

    resetSelect(tipoSelect, 'Selecione primeiro a profissão');
    setSelectDisabled(tipoSelect, true);

    if (!profissaoId) {
      return [];
    }

    const url =
      `${form.dataset.tiposUrl}?profissao_id=${encodeURIComponent(profissaoId)}`;

    console.debug('[Serviços] Carregando tipos de serviço.', {
      profissaoId,
      url,
    });

    const results = await loadOptions(
      tipoSelect,
      url,
      tipoStatus,
      'Selecione o tipo de serviço',
      'Nenhum tipo de serviço cadastrado para esta profissão'
    );

    console.debug('[Serviços] Tipos de serviço recebidos.', {
      profissaoId,
      quantidade: results.length,
      disabled: tipoSelect.disabled,
    });

    return results;
  }

  if (window.jQuery?.fn?.select2) {
    const $ = window.jQuery;

    $(setorSelect)
      .off('change.serviceDependencies')
      .on('change.serviceDependencies', handleSetorChange);

    $(areaSelect)
      .off('change.serviceDependencies')
      .on('change.serviceDependencies', handleAreaChange);

    $(profissaoSelect)
      .off('change.serviceDependencies')
      .on('change.serviceDependencies', handleProfissaoChange);
  } else {
    if (!setorSelect.dataset.serviceDependencyBound) {
      setorSelect.addEventListener('change', handleSetorChange);
      setorSelect.dataset.serviceDependencyBound = 'true';
    }

    if (!areaSelect.dataset.serviceDependencyBound) {
      areaSelect.addEventListener('change', handleAreaChange);
      areaSelect.dataset.serviceDependencyBound = 'true';
    }

    if (!profissaoSelect.dataset.serviceDependencyBound) {
      profissaoSelect.addEventListener('change', handleProfissaoChange);
      profissaoSelect.dataset.serviceDependencyBound = 'true';
    }
  }

  setSelectDisabled(areaSelect, !areaSelect.value);
  setSelectDisabled(profissaoSelect, !profissaoSelect.value);
  setSelectDisabled(tipoSelect, !tipoSelect.value);

  /*
   * Cadastro novo ou formulário devolvido com apenas Setor preenchido:
   * carrega automaticamente as áreas.
   *
   * Na edição, quando Área/Profissão/Tipo já possuem valor, os registros
   * existentes são preservados e não são apagados durante a inicialização.
   */
  if (setorSelect.value && !areaSelect.value) {
    void handleSetorChange();
  }
}

function initTaxonomySuggestions() {
  const config = document.querySelector('[data-suggest-setor-url]');
  const modal = document.querySelector('[data-taxonomy-modal]');
  if (!config || !modal) return;
  const suggestionForm = modal.querySelector('[data-taxonomy-suggestion-form]');
  const nameInput = suggestionForm.elements.nome;
  const title = modal.querySelector('[data-taxonomy-title]');
  const context = modal.querySelector('[data-taxonomy-context]');
  const error = modal.querySelector('[data-taxonomy-error]');
  const submit = suggestionForm.querySelector('[type="submit"]');
  const fields = {
    setor: document.getElementById('id_setor'),
    area: document.getElementById('id_area'),
    profissao: document.getElementById('id_profissao'),
    tipo_servico: document.getElementById('id_tipo_servico'),
  };
  const labels = {
    setor: 'Setor', area: 'Área profissional',
    profissao: 'Profissão', tipo_servico: 'Tipo de serviço',
  };
  let kind = '';

  function dependencyError(nextKind) {
    if (nextKind === 'area' && !fields.setor?.value) return 'Selecione primeiro o setor.';
    if (nextKind === 'profissao' && (!fields.setor?.value || !fields.area?.value)) {
      return 'Selecione primeiro o setor e a área profissional.';
    }
    if (nextKind === 'tipo_servico' && !fields.profissao?.value) {
      return 'Selecione primeiro a profissão.';
    }
    return '';
  }

  document.querySelectorAll('[data-suggest-taxonomy]').forEach((button) => {
    button.addEventListener('click', () => {
      const nextKind = button.dataset.suggestTaxonomy;
      const blocked = dependencyError(nextKind);
      if (blocked) {
        button.setCustomValidity(blocked);
        button.reportValidity();
        button.setCustomValidity('');
        return;
      }
      kind = nextKind;
      title.textContent = `Sugerir ${labels[kind].toLowerCase()}`;
      context.textContent = kind === 'setor'
        ? 'A sugestão ficará pendente de moderação e poderá ser usada por você.'
        : `A sugestão será vinculada à classificação selecionada e ficará pendente de moderação.`;
      nameInput.value = '';
      error.hidden = true;
      modal.showModal();
      nameInput.focus();
    });
  });

  modal.querySelectorAll('[data-taxonomy-close]').forEach((button) => {
    button.addEventListener('click', () => modal.close());
  });

  suggestionForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!nameInput.reportValidity()) return;
    const urlKey = `suggest${kind.replace(/_([a-z])/g, (_, char) => char.toUpperCase())}Url`;
    const body = new URLSearchParams({ nome: nameInput.value });
    if (fields.setor?.value) body.set('setor_id', fields.setor.value);
    if (fields.area?.value) body.set('area_id', fields.area.value);
    if (fields.profissao?.value) body.set('profissao_id', fields.profissao.value);
    submit.disabled = true;
    error.hidden = true;
    try {
      const csrf = document.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
      const response = await fetch(config.dataset[urlKey], {
        method: 'POST', credentials: 'same-origin',
        headers: {
          Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrf,
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        },
        body,
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Não foi possível enviar a sugestão.');
      const select = fields[kind];
      let option = Array.from(select.options).find((item) => String(item.value) === String(data.item.id));
      if (!option) {
        option = new Option(data.item.text, data.item.id, true, true);
        select.add(option);
      }
      option.selected = true;
      select.disabled = false;
      if (window.jQuery?.fn?.select2) window.jQuery(select).trigger('change');
      else select.dispatchEvent(new Event('change', { bubbles: true }));
      modal.close();
    } catch (requestError) {
      error.textContent = requestError.message;
      error.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });
}

document.addEventListener('change', (event) => {
  const provider = event.target.closest('[name="prestador_tipo"]');
  if (provider) updateProvider(provider);
});

document.addEventListener('DOMContentLoaded', () => {
  if (window.jQuery?.fn?.select2) {
    window.jQuery('select[name="setor"], select[name="area"], select[name="profissao"], select[name="tipo_servico"]').each(function () {
      if (window.jQuery(this).hasClass('select2-hidden-accessible')) return;
      window.jQuery(this).select2({
      width: '100%', allowClear: true, language: {
        noResults: () => 'Nenhum resultado encontrado',
        searching: () => 'Buscando...',
      },
      });
    });
  }
  initDependentServiceSelects();
  initTaxonomySuggestions();
  document.querySelectorAll('[data-image-input]').forEach((input) => {
    input.addEventListener('change', () => {
      const preview = input.parentElement.querySelector('[data-image-preview]');
      if (!preview) return;
      const file = input.files[0];
      if (!file) { preview.replaceChildren(); return; }
      const image = document.createElement('img');
      image.src = URL.createObjectURL(file);
      image.alt = 'Prévia da nova imagem principal';
      preview.replaceChildren(image);
    });
  });
  const linkList = document.querySelector('[data-link-list]');
  const linkTemplate = document.querySelector('[data-link-template]');
  const addLink = document.querySelector('[data-add-link]');
  let totalLinks = 0;
  if (linkList && linkTemplate && addLink) {
    addLink.addEventListener('click', () => {
      if (linkList.children.length >= 15) return;
      const fragment = linkTemplate.content.cloneNode(true);
      fragment.querySelectorAll('[name]').forEach((field) => { field.name = field.name.replace('TOTAL', String(totalLinks)); });
      totalLinks += 1;
      linkList.appendChild(fragment);
    });
    linkList.addEventListener('click', (event) => {
      const button = event.target.closest('[data-remove-link]');
      if (button) button.closest('[data-link-row]').remove();
    });
  }

  const provider = document.querySelector('[name="prestador_tipo"]');
  updateProvider(provider);

  const coverInput = document.querySelector('#imagem_capa');
  const coverName = document.querySelector('[data-cover-name]');
  if (coverInput && coverName) {
    coverInput.addEventListener('change', () => {
      coverName.textContent = coverInput.files[0]?.name || 'Nenhum arquivo selecionado';
    });
  }

  const galleryInput = document.querySelector('#galeria');
  const galleryName = document.querySelector('[data-gallery-name]');
  if (galleryInput && galleryName) {
    galleryInput.addEventListener('change', () => {
      const total = galleryInput.files.length;
      galleryName.textContent = total ? `${total} imagem(ns) selecionada(s)` : 'Nenhum arquivo selecionado';
    });
  }
});
