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
