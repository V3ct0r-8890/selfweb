const CACHE_VERSION = 'selfweb-v2';
const APP_SHELL = [
  './',
  './index.html',
  './manifest.json',
  './modules/news-feed.html',
  './modules/datecalc.html',
  './modules/pass-gen.html',
  './modules/PassCheck.html',
  './modules/subnetcal.html',
  './modules/EnergyConsumption-standalone.html',
  './modules/INS-offlineDB.html',
  './modules/Meal%20suggest%20tool-standalone.html',
  './modules/InterestCalculator.html',
  './modules/TimerTool.html',
  './modules/DigitalCamera-Lens-Calculator.html',
  './modules/TimeZoneViewer.html',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-512.png',
];

// Hosts this app calls for live data; never served from cache, and a network
// failure here must surface to the page rather than fall through silently.
const NETWORK_ONLY_HOSTS = [
  'en.wikipedia.org',
  'date.nager.at',
  'api.allorigins.win',
  'corsproxy.io',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  if (event.request.method !== 'GET') return;

  if (NETWORK_ONLY_HOSTS.includes(url.hostname)) {
    // Let these go straight to the network; do not intercept or cache.
    return;
  }

  if (url.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetchPromise = fetch(event.request)
        .then((response) => {
          if (response && response.ok) {
            const clone = response.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => cached);
      return cached || fetchPromise;
    })
  );
});
