// Service worker de QuiniPro: la app abre aunque la señal esté floja.
// La API nunca se guarda en caché (los picks y marcadores siempre van al servidor).
const VERSION = 'quinipro-v2';
const BASE = ['/', '/index.html', '/estilos.css', '/app.js', '/manifest.webmanifest',
  '/iconos/icono-192.png', '/iconos/icono-512.png', '/iconos/apple-180.png', '/iconos/favicon-32.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(BASE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.pathname.startsWith('/api/')) return;
  // Primero la red (para recibir actualizaciones al momento); si no hay señal, lo guardado.
  e.respondWith(
    fetch(e.request).then((r) => {
      if (r.ok && (url.origin === location.origin || url.host.endsWith('gstatic.com') || url.host.endsWith('googleapis.com'))) {
        const copia = r.clone();
        caches.open(VERSION).then((c) => c.put(e.request, copia));
      }
      return r;
    }).catch(() => caches.match(e.request).then((r) => r || caches.match('/index.html')))
  );
});
