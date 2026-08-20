// Service Worker — Section 23.4
// Cache strategy per route type

const CACHE_NAME = "fasal-kavach-v1";
const SHELL_CACHE = "fk-shell-v1";

// Cache-first assets (app shell + static)
const CACHE_FIRST_PATTERNS = [
  /\/_next\/static\//,
  /\/locales\//,
  /\/icons\//,
  /\/manifest\.json/,
];

// Network-first with fallback (advisory data)
const NETWORK_FIRST_PATTERNS = [
  /\/api\/v1\/.*\/advisories/,
  /\/api\/v1\/farms\//,
  /\/api\/v1\/weather\//,
];

// Network-only (never fake an answer)
const NETWORK_ONLY_PATTERNS = [
  /\/api\/v1\/ask/,
  /\/internal\//,
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then(cache =>
      cache.addAll(["/", "/onboarding"])
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME && k !== SHELL_CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = event.request.url;

  // Network-only: /ask and /internal
  if (NETWORK_ONLY_PATTERNS.some(p => p.test(url))) {
    return; // Let it go to network without caching
  }

  // Cache-first: static assets
  if (CACHE_FIRST_PATTERNS.some(p => p.test(url))) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return response;
        });
      })
    );
    return;
  }

  // Network-first with offline fallback: advisory data
  if (NETWORK_FIRST_PATTERNS.some(p => p.test(url))) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return response;
        })
        .catch(() => {
          return caches.match(event.request).then(cached => {
            if (cached) return cached;
            // Return an empty advisory list with a cache indicator
            return new Response(
              JSON.stringify({ farm_id: "", count: 0, advisories: [], _from_cache: true }),
              { headers: { "Content-Type": "application/json" } }
            );
          });
        })
    );
    return;
  }
});
