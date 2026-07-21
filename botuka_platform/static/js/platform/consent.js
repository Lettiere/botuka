(function () {
  'use strict';
  const panel = document.querySelector('[data-consent-panel]');
  const review = document.querySelector('[data-consent-review]');
  if (!panel) return;
  const cookieName = 'botuka_consent=';
  const hasChoice = document.cookie.split(';').some(item => item.trim().startsWith(cookieName));
  panel.hidden = hasChoice;
  function save(optional) {
    const value = encodeURIComponent(JSON.stringify({analytics: optional, marketing: optional, personalization: optional}));
    document.cookie = `${cookieName}${value}; Max-Age=31536000; Path=/; SameSite=Lax${location.protocol === 'https:' ? '; Secure' : ''}`;
    location.reload();
  }
  panel.addEventListener('click', function (event) {
    const button = event.target.closest('[data-consent]');
    if (button) save(button.dataset.consent === 'all');
  });
  if (review) review.addEventListener('click', function () { panel.hidden = false; });
})();
