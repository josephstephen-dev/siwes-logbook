const V = "siwes-v1";
const SHELL = ["/offline", "/static/css/tokens.css", "/static/css/base.css", "/static/css/auth.css",
  "/static/css/layout.css", "/static/css/components.css", "/static/css/paper.css",
  "/static/css/polish.css", "/static/img/favicon.svg"];
self.addEventListener("install", e => { e.waitUntil(caches.open(V).then(c => c.addAll(SHELL))); self.skipWaiting(); });
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith("/static/")) {          // static files only; refreshed in the background
    e.respondWith(caches.match(req).then(hit => {
      const net = fetch(req).then(r => { const copy = r.clone(); caches.open(V).then(c => c.put(req, copy)); return r; }).catch(() => hit);
      return hit || net;
    }));
    return;
  }
  if (req.mode === "navigate") e.respondWith(fetch(req).catch(() => caches.match("/offline")));
});