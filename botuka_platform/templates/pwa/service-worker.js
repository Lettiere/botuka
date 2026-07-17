{% load static %}
const BOTUKA_CACHE_VERSION = "botuka-pwa-v1";
const BOTUKA_STATIC_CACHE = `${BOTUKA_CACHE_VERSION}-static`;
const BOTUKA_PAGE_CACHE = `${BOTUKA_CACHE_VERSION}-pages`;

const APP_SHELL = [
  "{% url 'home' %}",
  "{% url 'offline' %}",
  "{% static 'css/platform/style.css' %}",
  "{% static 'js/platform/pwa.js' %}",
  "{% static 'img/icons/botuka-icon.svg' %}"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(BOTUKA_STATIC_CACHE)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) =>
        Promise.all(
          cacheNames
            .filter((cacheName) => !cacheName.startsWith(BOTUKA_CACHE_VERSION))
            .map((cacheName) => caches.delete(cacheName))
        )
      )
      .then(() => self.clients.claim())
  );
});

function isSameOrigin(request) {
  return new URL(request.url).origin === self.location.origin;
}

function shouldIgnore(request) {
  const url = new URL(request.url);
  return (
    request.method !== "GET" ||
    !isSameOrigin(request) ||
    url.pathname.startsWith("/admin/") ||
    url.pathname.startsWith("/media/") ||
    url.pathname === "/service-worker.js"
  );
}

async function networkFirst(request) {
  const cache = await caches.open(BOTUKA_PAGE_CACHE);

  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    return (
      (await cache.match(request)) ||
      (await caches.match("{% url 'offline' %}"))
    );
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(BOTUKA_STATIC_CACHE);
  const cached = await cache.match(request);
  const fetched = fetch(request)
    .then((response) => {
      if (response.ok) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => cached);

  return cached || fetched;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;

  if (shouldIgnore(request)) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request));
    return;
  }

  event.respondWith(staleWhileRevalidate(request));
});
