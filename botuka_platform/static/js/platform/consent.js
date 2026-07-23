(function () {
  'use strict';

  const COOKIE_NAME = 'botuka_consent';
  const STORAGE_KEY = 'botuka_consent';
  const MAX_AGE = 60 * 60 * 24 * 365;
  const panel = document.querySelector('[data-consent-panel]');
  const review = document.querySelector('[data-consent-review]');

  if (!panel) return;

  function normalize(value) {
    if (!value || typeof value !== 'object') return null;
    if (typeof value.analytics !== 'boolean' || typeof value.marketing !== 'boolean') return null;
    return {
      analytics: value.analytics,
      marketing: value.marketing,
      personalization: value.personalization === true,
      version: 1,
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
      + '; Max-Age=' + MAX_AGE + '; Path=/; SameSite=Lax' + secure;
    try {
      window.localStorage.setItem(STORAGE_KEY, serialized);
    } catch (_error) {
      // O cookie de primeira parte continua sendo a fonte principal.
    }
  }

  function setVisibility(hasChoice) {
    panel.hidden = hasChoice;
    if (review) review.hidden = !hasChoice;
  }

  function save(allowOptional) {
    const choice = {
      analytics: allowOptional,
      marketing: allowOptional,
      personalization: allowOptional,
      version: 1,
    };
    writeChoice(choice);
    setVisibility(true);
    window.dispatchEvent(new CustomEvent('botuka:consent-updated', {detail: choice}));
  }

  const storedChoice = readCookie() || readStorage();
  if (storedChoice && !readCookie()) writeChoice(storedChoice);
  setVisibility(Boolean(storedChoice));

  panel.addEventListener('click', function (event) {
    const button = event.target.closest('[data-consent]');
    if (!button) return;
    save(button.dataset.consent === 'all');
  });

  if (review) {
    review.addEventListener('click', function () {
      panel.hidden = false;
      review.hidden = true;
      const firstButton = panel.querySelector('[data-consent]');
      if (firstButton) firstButton.focus();
    });
  }
})();
