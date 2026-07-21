(function () {
  'use strict';
  document.addEventListener('click', function (event) {
    const link = event.target.closest('a[href]');
    if (!link || typeof window.botukaTrack !== 'function') return;
    const href = link.getAttribute('href') || '';
    let eventName = '';
    let linkType = '';
    if (href.startsWith('https://wa.me/') || href.includes('whatsapp.com')) {
      eventName = 'click_whatsapp'; linkType = 'whatsapp';
    } else if (href.startsWith('tel:')) {
      eventName = 'click_phone'; linkType = 'phone';
    } else if (href.startsWith('mailto:')) {
      eventName = 'click_email'; linkType = 'email';
    }
    if (eventName) window.botukaTrack(eventName, {link_type: linkType, page_type: document.body.dataset.pageType || 'page'});
  });
})();
