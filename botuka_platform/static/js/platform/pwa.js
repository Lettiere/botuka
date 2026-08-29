(function () {
  'use strict';

  const INSTALL_STATE_KEY = 'botuka_pwa_install_state';
  const UPDATE_RELOAD_KEY = 'botuka_pwa_update_reload';
  const DISMISS_DAYS = 7;
  const promptElement = document.querySelector('[data-pwa-install-prompt]');
  const updateElement = document.querySelector('[data-pwa-update-notice]');
  const updateButton = document.querySelector('[data-pwa-update]');
  let deferredInstallPrompt = null;
  let waitingWorker = null;
  let updateAccepted = false;
  let reloadStarted = false;
  let previousFocus = null;

  function isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches
      || window.navigator.standalone === true;
  }

  function isAndroid() {
    return /Android/i.test(window.navigator.userAgent || '');
  }

  function readInstallState() {
    try {
      return JSON.parse(window.localStorage.getItem(INSTALL_STATE_KEY)) || {};
    } catch (_error) {
      return {};
    }
  }

  function writeInstallState(state) {
    try {
      window.localStorage.setItem(INSTALL_STATE_KEY, JSON.stringify(state));
    } catch (_error) {
      // A detecção standalone ainda impede convites em aplicativos instalados.
    }
  }

  function invitationAllowed() {
    if (!promptElement || !isAndroid() || isStandalone()) return false;
    const state = readInstallState();
    if (state.status === 'installed') return false;
    return !state.nextPromptAt || Date.now() >= state.nextPromptAt;
  }

  function hidePrompt() {
    if (!promptElement) return;
    promptElement.classList.remove('is-visible');
    promptElement.hidden = true;
    document.body.classList.remove('has-pwa-prompt');
    if (previousFocus && typeof previousFocus.focus === 'function') {
      previousFocus.focus();
    }
    previousFocus = null;
  }

  function showPrompt() {
    if (!invitationAllowed() || !deferredInstallPrompt) return;
    previousFocus = document.activeElement;
    promptElement.hidden = false;
    document.body.classList.add('has-pwa-prompt');
    window.requestAnimationFrame(function () {
      promptElement.classList.add('is-visible');
      const installButton = promptElement.querySelector('[data-pwa-install]');
      if (installButton) installButton.focus();
    });
  }

  function dismissPrompt() {
    writeInstallState({
      status: 'dismissed',
      dismissedAt: Date.now(),
      nextPromptAt: Date.now() + (DISMISS_DAYS * 24 * 60 * 60 * 1000),
    });
    deferredInstallPrompt = null;
    hidePrompt();
  }

  function markInstalled() {
    writeInstallState({status: 'installed', installedAt: Date.now()});
    deferredInstallPrompt = null;
    hidePrompt();
  }

  window.addEventListener('beforeinstallprompt', function (event) {
    event.preventDefault();
    if (!isAndroid() || isStandalone()) return;
    deferredInstallPrompt = event;
    showPrompt();
  });

  window.addEventListener('appinstalled', markInstalled);
  const displayModeQuery = window.matchMedia('(display-mode: standalone)');
  const displayModeChanged = function (event) {
    if (event.matches) markInstalled();
  };
  if (typeof displayModeQuery.addEventListener === 'function') {
    displayModeQuery.addEventListener('change', displayModeChanged);
  } else if (typeof displayModeQuery.addListener === 'function') {
    displayModeQuery.addListener(displayModeChanged);
  }

  if (promptElement) {
    promptElement.addEventListener('click', function (event) {
      if (event.target.closest('[data-pwa-dismiss]')) {
        dismissPrompt();
        return;
      }
      if (!event.target.closest('[data-pwa-install]') || !deferredInstallPrompt) return;
      const installPrompt = deferredInstallPrompt;
      deferredInstallPrompt = null;
      installPrompt.prompt();
      installPrompt.userChoice.then(function (choice) {
        if (choice.outcome === 'accepted') {
          markInstalled();
        } else {
          dismissPrompt();
        }
      });
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !promptElement.hidden) dismissPrompt();
    });
  }

  if (isStandalone()) markInstalled();

  if (!('serviceWorker' in navigator)) return;

  function showUpdate(worker) {
    waitingWorker = worker;
    if (updateElement) updateElement.hidden = false;
  }

  if (updateButton) {
    updateButton.addEventListener('click', function () {
      if (!waitingWorker) return;
      updateAccepted = true;
      updateButton.disabled = true;
      waitingWorker.postMessage({type: 'SKIP_WAITING'});
    });
  }

  navigator.serviceWorker.addEventListener('controllerchange', function () {
    if (!updateAccepted || reloadStarted) return;
    if (window.sessionStorage.getItem(UPDATE_RELOAD_KEY)) return;
    reloadStarted = true;
    window.sessionStorage.setItem(UPDATE_RELOAD_KEY, String(Date.now()));
    window.location.reload();
  });

  window.setTimeout(function () {
    window.sessionStorage.removeItem(UPDATE_RELOAD_KEY);
  }, 10000);

  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/service-worker.js', {scope: '/'}).then(function (registration) {
      if (registration.waiting && navigator.serviceWorker.controller) {
        showUpdate(registration.waiting);
      }
      registration.addEventListener('updatefound', function () {
        const worker = registration.installing;
        if (!worker) return;
        worker.addEventListener('statechange', function () {
          if (worker.state === 'installed' && navigator.serviceWorker.controller) {
            showUpdate(worker);
          }
        });
      });
      registration.update().catch(function () {
        return null;
      });
      window.setInterval(function () {
        registration.update().catch(function () {
          return null;
        });
      }, 60 * 60 * 1000);
    }).catch(function () {
      return null;
    });
  });
})();
