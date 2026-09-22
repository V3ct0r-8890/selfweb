// Bump on every release that changes any APP_SHELL file: this is what makes
// browsers see a new version and offer the user the update.
// Matches APP_VERSION in index.html (aa.bb.ccc).
const CACHE_VERSION = 'selfweb-1.01.007';
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
  './modules/fonts/DSEG7Classic-Bold.woff2',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-512.png',
];

// Third-party scripts the tools need to work (styling, password strength).
// Precached with the app so tools still work offline. Versions are pinned in the
// pages' <script> tags; change both together.
const CDN_ASSETS = [
  { url: 'https://cdn.tailwindcss.com/3.4.17', mode: 'no-cors' }, // no CORS headers: stored opaque
  { url: 'https://cdnjs.cloudflare.com/ajax/libs/zxcvbn/4.4.2/zxcvbn.js', mode: 'cors' },
];
const CDN_URLS = CDN_ASSETS.map((asset) => asset.url);

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
      Promise.all([
        cache.addAll(APP_SHELL.map((url) => new Request(url, { cache: 'reload' }))),
        // addAll() rejects opaque responses, so CDN files are fetched and stored one by one.
        // A CDN outage must not block the update: a miss here is cached on first use instead.
        ...CDN_ASSETS.map(({ url, mode }) =>
          fetch(new Request(url, { mode, cache: 'reload' }))
            .then((response) => {
              if (response.type !== 'opaque' && !response.ok) {
                throw new Error(`HTTP ${response.status}`);
              }
              return cache.put(url, response);
            })
            .catch((err) => console.warn(`CDN precache failed for ${url}:`, err))
        ),
      ])
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

  if (CDN_URLS.includes(url.href)) {
    event.respondWith(
      caches.match(url.href).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response.type === 'opaque' || response.ok) {
            const clone = response.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(url.href, clone));
          }
          return response;
        });
      })
    );
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
