{% load static %}
const BOTUKA_CACHE_VERSION = "botuka-pwa-v2";
const BOTUKA_STATIC_CACHE = `${BOTUKA_CACHE_VERSION}-static`;

const APP_SHELL = [
  "{% url 'offline' %}",
  "{% static 'css/platform/style.css' %}",
  "{% static 'css/platform/public-shell.css' %}",
  "{% static 'js/platform/pwa.js' %}",
  "{% static 'img/icons/botuka-icon.svg' %}",
  "{% static 'img/icons/botuka-icon-192.png' %}",
  "{% static 'img/icons/botuka-icon-512.png' %}"
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

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
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
    url.pathname.startsWith("/painel/") ||
    url.pathname.startsWith("/gestao/") ||
    url.pathname.startsWith("/conta/") ||
    url.pathname.startsWith("/media/") ||
    url.pathname.startsWith("/qrcode/") ||
    url.pathname.startsWith("/compartilhar/") ||
    url.pathname === "/service-worker.js"
  );
}

async function networkFirst(request) {
  try {
    return await fetch(request);
  } catch (error) {
    return await caches.match("{% url 'offline' %}");
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

  if (["style", "script", "image", "font"].includes(request.destination)) {
    event.respondWith(staleWhileRevalidate(request));
  }
});
