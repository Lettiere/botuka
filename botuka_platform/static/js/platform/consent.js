(function () {
  'use strict';

  const COOKIE_NAME = 'botuka_consent';
  const STORAGE_KEY = 'botuka_consent';
  const panel = document.querySelector('[data-consent-panel]');

  if (!panel) return;

  const policyVersion = panel.dataset.policyVersion;
  const maxAgeDays = Number.parseInt(panel.dataset.consentMaxAgeDays, 10) || 365;
  const maxAgeSeconds = maxAgeDays * 24 * 60 * 60;

  function normalize(value) {
    if (!value || typeof value !== 'object') return null;
    if (value.version !== policyVersion) return null;
    if (typeof value.analytics !== 'boolean' || typeof value.marketing !== 'boolean') return null;
    if (value.expiresAt && Date.now() >= value.expiresAt) return null;
    return {
      analytics: value.analytics,
      marketing: value.marketing,
      personalization: value.personalization === true,
      version: policyVersion,
      consentedAt: value.consentedAt || Date.now(),
      expiresAt: value.expiresAt || Date.now() + (maxAgeSeconds * 1000),
    };
  }

  function readCookie() {
    const prefix = COOKIE_NAME + '=';
    const item = document.cookie.split(';').map(function (part) {
      return part.trim();
    }).find(function (part) {
      return part.startsWith(prefix);
    });
    if (!item) return null;
    try {
      return normalize(JSON.parse(decodeURIComponent(item.slice(prefix.length))));
    } catch (_error) {
      return null;
    }
  }

  function readStorage() {
    try {
      return normalize(JSON.parse(window.localStorage.getItem(STORAGE_KEY)));
    } catch (_error) {
      return null;
    }
  }

  function writeChoice(choice) {
    const serialized = JSON.stringify(choice);
    const secure = window.location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = COOKIE_NAME + '=' + encodeURIComponent(serialized)
      + '; Max-Age=' + maxAgeSeconds + '; Path=/; SameSite=Lax' + secure;
    try {
      window.localStorage.setItem(STORAGE_KEY, serialized);
    } catch (_error) {
      // O cookie de primeira parte continua sendo a fonte principal.
    }
  }

  function hideCompletely() {
    panel.hidden = true;
    panel.setAttribute('aria-hidden', 'true');
  }

  function show() {
    panel.hidden = false;
    panel.removeAttribute('aria-hidden');
  }

  function save(allowOptional) {
    const now = Date.now();
    const choice = {
      analytics: allowOptional,
      marketing: allowOptional,
      personalization: allowOptional,
      version: policyVersion,
      consentedAt: now,
      expiresAt: now + (maxAgeSeconds * 1000),
    };
    writeChoice(choice);
    hideCompletely();
    window.dispatchEvent(new CustomEvent('botuka:consent-updated', {detail: choice}));
    if (allowOptional) window.location.reload();
  }

  const storedChoice = readCookie() || readStorage();
  if (storedChoice) {
    if (!readCookie()) writeChoice(storedChoice);
    hideCompletely();
  } else {
    show();
  }

  panel.addEventListener('click', function (event) {
    const button = event.target.closest('[data-consent]');
    if (!button) return;
    save(button.dataset.consent === 'all');
  });
})();
