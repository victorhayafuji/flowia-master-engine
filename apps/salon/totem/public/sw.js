// Minimal app-shell service worker for the kiosk PWA (installability + offline shell).
// Cache-first for the shell; network-first for everything else (API calls bypass cache).
const CACHE = "totem-shell-v1";
const SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  // Never cache API traffic — the kiosk must always hit the live backend.
  if (request.method !== "GET" || new URL(request.url).pathname.includes("/api/")) return;
  // Navigations: serve the cached shell so the kiosk survives flaky networks.
  if (request.mode === "navigate") {
    event.respondWith(caches.match("/index.html").then((r) => r || fetch(request)));
    return;
  }
  event.respondWith(caches.match(request).then((r) => r || fetch(request)));
});
