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
}

async function loadOptions(select, url, statusElement, emptyLabel) {
  resetSelect(select, 'Carregando...');
  select.disabled = true;
  if (statusElement) {
    statusElement.textContent = 'Carregando opções...';
    statusElement.classList.remove('text-danger');
  }

  try {
    const response = await fetch(url, {
      headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível carregar as opções.');
    resetSelect(select, emptyLabel);
    data.results.forEach((item) => select.add(new Option(item.text, item.id)));
    if (statusElement) {
      statusElement.textContent = data.results.length
        ? `${data.results.length} opção(ões) disponível(is).`
        : 'Nenhuma opção ativa foi encontrada para a seleção anterior.';
    }
    return data.results;
  } catch (error) {
    resetSelect(select, 'Não foi possível carregar');
    if (statusElement) {
      statusElement.textContent = error.message;
      statusElement.classList.add('text-danger');
    }
    return [];
  } finally {
    select.disabled = false;
  }
}

document.addEventListener('change', async (event) => {
  const provider = event.target.closest('[name="prestador_tipo"]');
  if (provider) updateProvider(provider);

  const setor = event.target.closest('select[name="setor"]');
  const area = event.target.closest('select[name="area"]');
  const areaSelect = document.querySelector('select[name="area"]');
  const profissaoSelect = document.querySelector('select[name="profissao"]');

  if (setor && areaSelect && profissaoSelect) {
    resetSelect(areaSelect, 'Selecione primeiro o setor');
    resetSelect(profissaoSelect, 'Selecione primeiro a área');
    if (setor.value) {
      const areas = await loadOptions(
        areaSelect,
        `/painel/servicos/ajax/areas/?setor=${encodeURIComponent(setor.value)}`,
        document.querySelector('[data-dependency-status="area"]'),
        'Selecione a área profissional',
      );
      if (!areas.length) {
        await loadOptions(
          profissaoSelect,
          `/painel/servicos/ajax/profissoes/?setor=${encodeURIComponent(setor.value)}`,
          document.querySelector('[data-dependency-status="profissao"]'),
          'Selecione a profissão',
        );
      }
    }
  } else if (area && profissaoSelect) {
    resetSelect(profissaoSelect, 'Selecione primeiro a área');
    if (area.value) {
      await loadOptions(
        profissaoSelect,
        `/painel/servicos/ajax/profissoes/?area=${encodeURIComponent(area.value)}`,
        document.querySelector('[data-dependency-status="profissao"]'),
        'Selecione a profissão',
      );
    } else {
      const setorAtual = document.querySelector('select[name="setor"]')?.value;
      if (setorAtual) {
        await loadOptions(
          profissaoSelect,
          `/painel/servicos/ajax/profissoes/?setor=${encodeURIComponent(setorAtual)}`,
          document.querySelector('[data-dependency-status="profissao"]'),
          'Selecione a profissão',
        );
      }
    }
  }
});

document.addEventListener('DOMContentLoaded', () => {
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
