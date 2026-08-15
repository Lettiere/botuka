(function () {
  'use strict';
  const endpoint = '/api/analytics/events/';
  const consentCookie = 'botuka_consent=';
  const allowedContextKeys = ['searchTerm', 'resultsCount', 'resultType', 'position', 'category', 'method', 'context', 'pageType', 'contentName'];

  function consentAllowed() {
    const raw = document.cookie.split(';').map(item => item.trim()).find(item => item.startsWith(consentCookie));
    if (!raw) return false;
    try {
      const value = JSON.parse(decodeURIComponent(raw.slice(consentCookie.length)));
      const policyVersion = document.querySelector('[data-consent-panel]')?.dataset.policyVersion;
      return value.analytics === true
        && (!policyVersion || value.version === policyVersion)
        && Number(value.expiresAt) > Date.now();
    }
    catch (_error) { return false; }
  }
  function id(storage, key) {
    let value = storage.getItem(key);
    if (!value) {
      value = crypto.randomUUID ? crypto.randomUUID() : [Date.now(), Math.random(), Math.random()].join('-');
      storage.setItem(key, value);
    }
    return value;
  }
  function csrf() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
  }
  function deviceType() {
    const width = window.innerWidth;
    return width < 768 ? 'mobile' : width < 1024 ? 'tablet' : 'desktop';
  }
  function attribution() {
    const params = new URLSearchParams(location.search);
    const current = {
      source: params.get('utm_source') || (document.referrer ? new URL(document.referrer, location.href).hostname : 'direct'),
      medium: params.get('utm_medium') || (document.referrer ? 'referral' : 'none'),
      campaign: params.get('utm_campaign') || '',
      term: params.get('utm_term') || '',
      content: params.get('utm_content') || '',
      gclid: params.get('gclid') || '', gbraid: params.get('gbraid') || '', wbraid: params.get('wbraid') || '',
      landing_path: location.pathname,
    };
    let first = {};
    try {
      first = JSON.parse(localStorage.getItem('botuka_first_touch') || '{}');
      if (!first.source) { first = current; localStorage.setItem('botuka_first_touch', JSON.stringify(first)); }
      sessionStorage.setItem('botuka_last_touch', JSON.stringify(current));
    } catch (_error) {}
    return Object.assign({}, current, {
      first_source: first.source || '', first_medium: first.medium || '', first_campaign: first.campaign || '',
    });
  }
  function cleanMetadata(data) {
    const metadata = {};
    allowedContextKeys.forEach(key => {
      if (data[key] !== undefined && data[key] !== '') {
        metadata[key.replace(/[A-Z]/g, letter => '_' + letter.toLowerCase())] = data[key];
      }
    });
    return metadata;
  }
  function dedupe(eventName, data) {
    const bucket = Math.floor(Date.now() / 300000);
    return [id(sessionStorage, 'botuka_session_id'), eventName, data.objectType || '', data.objectId || '', data.context || location.pathname, bucket].join('|');
  }
  function track(eventName, data) {
    data = data || {};
    if (!consentAllowed()) return;
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push(Object.assign({event: eventName}, cleanMetadata(data), {
      object_type: data.objectType || '', object_id: data.objectId || '',
    }));
    const payload = {
      event_name: eventName,
      visitor_id: id(localStorage, 'botuka_visitor_id'),
      session_id: id(sessionStorage, 'botuka_session_id'),
      object_type: data.objectType || '',
      object_id: data.objectId || null,
      path: location.pathname,
      referrer: document.referrer,
      device_type: deviceType(),
      attribution: attribution(),
      metadata: cleanMetadata(data),
      dedupe_key: data.dedupeKey || dedupe(eventName, data),
    };
    fetch(endpoint, {
      method: 'POST', credentials: 'same-origin', keepalive: true,
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
      body: JSON.stringify(payload),
    }).catch(function () {});
  }
  window.BotukaAnalytics = {track: track};
  window.botukaTrack = function (eventName, data) { track(eventName, data); };

  document.addEventListener('DOMContentLoaded', function () {
    track('page_view', {pageType: document.body.dataset.pageType || 'public'});
    const page = document.querySelector('[data-analytics-event]');
    if (page && page.dataset.analyticsEvent) {
      track(page.dataset.analyticsEvent, {
        objectType: page.dataset.objectType, objectId: page.dataset.objectId,
        searchTerm: page.dataset.searchTerm, resultsCount: Number(page.dataset.resultsCount || 0),
        context: page.dataset.analyticsContext || location.pathname,
      });
    }
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting || entry.intersectionRatio < .5) return;
        const item = entry.target;
        if (item.dataset.analyticsSeen || !item.dataset.analyticsImpression) return;
        item.dataset.analyticsSeen = '1';
        track(item.dataset.analyticsImpression, {
          objectType: item.dataset.objectType, objectId: item.dataset.objectId,
          searchTerm: item.dataset.searchTerm, position: Number(item.dataset.position || 0),
          context: item.dataset.analyticsContext || 'listing',
        });
        observer.unobserve(item);
      });
    }, {threshold: [.5]});
    document.querySelectorAll('[data-analytics-impression]').forEach(item => observer.observe(item));
    setTimeout(function () {
      if (!document.hidden) track('engaged_view', {
        objectType: page?.dataset.objectType, objectId: page?.dataset.objectId,
        context: location.pathname,
      });
    }, 15000);
  });

  document.addEventListener('click', function (event) {
    const selected = event.target.closest('[data-analytics-select]');
    if (selected) track(selected.dataset.analyticsSelect, {
      objectType: selected.dataset.objectType, objectId: selected.dataset.objectId,
      searchTerm: selected.dataset.searchTerm, resultType: selected.dataset.resultType,
      position: Number(selected.dataset.position || 0), context: 'search',
    });
    const link = event.target.closest('a[href]');
    if (!link) return;
    const href = link.getAttribute('href') || '';
    const context = link.closest('[data-object-type]') || document.querySelector('[data-analytics-event]');
    const base = {objectType: context?.dataset.objectType, objectId: context?.dataset.objectId, context: context?.dataset.analyticsContext || location.pathname};
    if (href.startsWith('https://wa.me/') || href.includes('whatsapp.com')) track('whatsapp_click', base);
    else if (href.startsWith('tel:')) track('phone_click', base);
    else if (link.dataset.analyticsDirections !== undefined) track('directions_click', base);
    else if (/^https?:\/\//.test(href) && new URL(href, location.href).origin !== location.origin) track('website_click', base);
  });
})();
