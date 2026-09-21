// Bump on every release that changes any APP_SHELL file: this is what makes
// browsers see a new version and offer the user the update.
const CACHE_VERSION = 'selfweb-v4';
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
  'api.rss2json.com',
];

self.addEventListener('install', (event) => {
  // cache: 'reload' bypasses the HTTP cache so a new version never precaches stale files.
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) =>
      cache.addAll(APP_SHELL.map((url) => new Request(url, { cache: 'reload' })))
    )
  );
  // No skipWaiting() here: a new version waits until the user accepts the update.
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
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

  // Cache-first with no background refresh: the app only changes when the user
  // accepts an update, so every page and tool frame comes from the same version.
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response && response.ok) {
          const clone = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(event.request, clone));
        }
        return response;
      });
    })
  );
});
