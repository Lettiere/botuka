// Helper CSRF único para requisições que alteram estado.
window.Botuka = window.Botuka || {};
window.Botuka.getCookie = function (name) {
  const prefix = `${name}=`;
  const cookie = document.cookie.split(';').map(value => value.trim())
    .find(value => value.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
};

window.Botuka.csrfFetch = async function (url, options = {}) {
  const headers = new Headers(options.headers || {});
  const method = (options.method || 'GET').toUpperCase();
  if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
    const token = window.Botuka.getCookie('csrftoken');
    if (token) headers.set('X-CSRFToken', token);
  }
  const response = await fetch(url, {
    ...options,
    headers,
    credentials: options.credentials || 'same-origin',
  });
  if (response.status === 403) {
    window.dispatchEvent(new CustomEvent('botuka:csrf-failed'));
  }
  return response;
};

window.addEventListener('botuka:csrf-failed', function () {
  window.alert('Sua sessão ou formulário expirou. Atualize a página e tente novamente.');
});

// servicos.js — Lógica dinâmica do formulário de cadastro de serviços

(function() {
  // Localiza os elementos requeridos
  const prestadorTipo = document.getElementById('id_prestador_tipo');
  const empresaSelect = document.getElementById('id_empresa');
  const empresaWrapper = document.getElementById('empresaFieldWrapper') || document.querySelector('[data-empresa-field]');

  // Se qualquer elemento necessário não existir, sair silenciosamente
  if (!prestadorTipo || !empresaSelect || !empresaWrapper) {
    return;
  }

  // Função para identificar se o valor selecionado corresponde a Pessoa Física ou Pessoa Jurídica
  function tipoPrestador(valor) {
    if (!valor || typeof valor !== 'string') return '';
    const v = valor.trim().toUpperCase();
    // Considera variantes para cada tipo (regra 4)
    const fisicas = ['PF', 'PESSOA_FISICA', 'FISICA'];
    const juridicas = ['PJ', 'EMPRESA', 'PESSOA_JURIDICA', 'JURIDICA'];
    if (fisicas.includes(v)) return 'PF';
    if (juridicas.includes(v)) return 'PJ';
    return '';
  }

  // Função principal de controle do campo empresa
  function atualizarCampoEmpresa() {
    const valorAtual = prestadorTipo.value;
    const tipo = tipoPrestador(valorAtual);

    // Para depuração
    console.log("Prestador:", valorAtual);

    if (tipo === 'PF') {
      // Esconde o bloco empresa
      empresaWrapper.style.display = 'none';

      // Limpa seleção do select
      empresaSelect.value = '';
      if (empresaSelect.tagName.toLowerCase() === 'select') {
        // Se a opção vazia não existir, adiciona sem duplicação
        if (!empresaSelect.querySelector('option[value=""]')) {
          const opt = document.createElement('option');
          opt.value = '';
          opt.textContent = '---------';
          empresaSelect.insertBefore(opt, empresaSelect.firstChild);
        }
      }

      // Remove required e desabilita select
      empresaSelect.removeAttribute('required');
      empresaSelect.setAttribute('disabled', 'disabled');
    }
    else if (tipo === 'PJ') {
      // Mostra o bloco empresa
      empresaWrapper.style.display = '';

      // Habilita e torna required
      empresaSelect.removeAttribute('disabled');
      empresaSelect.setAttribute('required', 'required');
    }
    // Caso valor não seja reconhecido
    else {
      // Opcional: deixa o campo empresa visível normalmente, mas não required
      empresaWrapper.style.display = '';
      empresaSelect.removeAttribute('required');
      empresaSelect.removeAttribute('disabled');
    }
  }

  // Executar ao carregar a página
  atualizarCampoEmpresa();

  // Executar sempre que mudar o tipo de prestador
  prestadorTipo.addEventListener('change', atualizarCampoEmpresa);

})();

// Navegação acessível dos carrosséis nativos da HOME (touch continua disponível).
document.addEventListener('click', function (event) {
  const button = event.target.closest('[data-city-scroll]');
  if (!button) return;
  const strip = document.getElementById(button.dataset.cityScroll);
  if (!strip) return;
  const direction = Number(button.dataset.direction) || 1;
  strip.scrollBy({ left: direction * Math.min(strip.clientWidth * 0.85, 620), behavior: 'smooth' });
});

// Carrega players validados apenas sob ação do usuário.
document.addEventListener('click', function (event) {
  const button = event.target.closest('[data-video-src]');
  if (!button) return;
  const source = button.dataset.videoSrc || '';
  if (!source.startsWith('https://www.youtube-nocookie.com/embed/')) return;
  const iframe = document.createElement('iframe');
  iframe.src = source;
  iframe.title = button.getAttribute('aria-label') || 'Vídeo da YTv Botuka';
  iframe.loading = 'lazy';
  iframe.allow = 'accelerometer; encrypted-media; picture-in-picture';
  iframe.allowFullscreen = true;
  button.closest('[data-video-shell]').replaceChildren(iframe);
});
// Abas progressivas do perfil do usuário.
  document.addEventListener("DOMContentLoaded", function () {
    const tabButtons = Array.from(document.querySelectorAll("[data-profile-tab]"));
    const tabPanels = Array.from(document.querySelectorAll(".profile-tab-panel"));
    const mobileSelect = document.getElementById("profileMobileSelect");
    const sectionTitle = document.getElementById("profileSectionTitle");
    const sectionDescription = document.getElementById("profileSectionDescription");

    const tabMeta = {
      "tab-geral": {
        title: "Visão geral",
        description: "Consulte um resumo das principais informações da sua conta."
      },
      "tab-dados": {
        title: "Dados pessoais",
        description: "Atualize suas informações pessoais e os dados utilizados no seu perfil."
      },
      "tab-foto": {
        title: "Foto e apresentação",
        description: "Escolha sua imagem de perfil e escreva uma apresentação sobre você."
      },
      "tab-contato": {
        title: "Contato",
        description: "Mantenha seus canais de contato e localização sempre atualizados."
      },
      "tab-documentos": {
        title: "Documentos",
        description: "Cadastre e revise os documentos necessários para usar os recursos da plataforma."
      },
      "tab-atividades": {
        title: "Perfis e atividades",
        description: "Consulte seu perfil principal, perfis adicionais e permissões vinculadas."
      },
      "tab-empresas": {
        title: "Empresas vinculadas",
        description: "Visualize empresas relacionadas ao seu usuário e empresas das quais você é proprietário."
      },
      "tab-seguranca": {
        title: "Segurança",
        description: "Consulte o status e os níveis de acesso associados à sua conta."
      }
    };

    function normalizeTab(tabId) {
      const exists = tabPanels.some(panel => panel.id === tabId);
      return exists ? tabId : "tab-geral";
    }

    function activateTab(tabId, updateHash = true, scrollToContent = false) {
      tabId = normalizeTab(tabId);

      tabButtons.forEach(button => {
        const isActive = button.dataset.profileTab === tabId;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-selected", isActive ? "true" : "false");
      });

      tabPanels.forEach(panel => {
        panel.classList.toggle("active", panel.id === tabId);
      });

      if (mobileSelect) {
        mobileSelect.value = tabId;
      }

      const meta = tabMeta[tabId] || tabMeta["tab-geral"];

      if (sectionTitle) {
        sectionTitle.textContent = meta.title;
      }

      if (sectionDescription) {
        sectionDescription.textContent = meta.description;
      }

      if (updateHash) {
        history.replaceState(null, "", "#" + tabId);
      }

      if (scrollToContent && window.innerWidth <= 820) {
        document.querySelector(".profile-content-card")?.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });
      }
    }

    tabButtons.forEach(button => {
      button.addEventListener("click", function () {
        activateTab(button.dataset.profileTab, true, false);
      });
    });

    if (mobileSelect) {
      mobileSelect.addEventListener("change", function () {
        activateTab(this.value, true, true);
      });
    }

    const currentHash = window.location.hash.replace("#", "");
    activateTab(currentHash || "tab-geral", false, false);

    window.addEventListener("hashchange", function () {
      activateTab(window.location.hash.replace("#", ""), false, true);
    });

    const formWithErrors = document.querySelector(".errorlist");
    if (formWithErrors) {
      const panel = formWithErrors.closest(".profile-tab-panel");

      if (panel) {
        activateTab(panel.id, true, false);
      }
    }
  });
