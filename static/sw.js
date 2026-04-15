var CACHE_NAME = 'printcostcalc-v3';
var STATIC_ASSETS = [
    '/',
    '/static/css/style.css',
    '/static/js/calculator.js',
    '/static/js/sync.js',
    '/static/js/spoolman.js',
    '/static/icons/icon.svg',
    '/manifest.json',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css'
];

// Install: cache static assets
self.addEventListener('install', function (e) {
    e.waitUntil(
        caches.open(CACHE_NAME).then(function (cache) {
            return cache.addAll(STATIC_ASSETS).catch(function () {
                // Some assets may fail (CDN offline) — that's ok
                return Promise.resolve();
            });
        })
    );
    self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', function (e) {
    e.waitUntil(
        caches.keys().then(function (names) {
            return Promise.all(
                names.filter(function (n) { return n !== CACHE_NAME; })
                    .map(function (n) { return caches.delete(n); })
            );
        })
    );
    self.clients.claim();
});

// Fetch strategy
self.addEventListener('fetch', function (e) {
    var url = new URL(e.request.url);

    // API calls: network first, no cache fallback (IndexedDB handles offline data)
    if (url.pathname.startsWith('/api/')) {
        e.respondWith(
            fetch(e.request).catch(function () {
                return new Response(JSON.stringify({ error: 'Offline' }), {
                    headers: { 'Content-Type': 'application/json' },
                    status: 503
                });
            })
        );
        return;
    }

    // Static assets: network first, fallback to cache
    if (url.pathname.startsWith('/static/') || STATIC_ASSETS.indexOf(url.href) !== -1) {
        e.respondWith(
            fetch(e.request).then(function (resp) {
                if (resp.ok) {
                    var clone = resp.clone();
                    caches.open(CACHE_NAME).then(function (cache) {
                        cache.put(e.request, clone);
                    });
                }
                return resp;
            }).catch(function () {
                return caches.match(e.request);
            })
        );
        return;
    }

    // HTML pages: network first, fallback to cache
    if (e.request.headers.get('Accept') && e.request.headers.get('Accept').indexOf('text/html') !== -1) {
        e.respondWith(
            fetch(e.request).then(function (resp) {
                if (resp.ok) {
                    var clone = resp.clone();
                    caches.open(CACHE_NAME).then(function (cache) {
                        cache.put(e.request, clone);
                    });
                }
                return resp;
            }).catch(function () {
                return caches.match(e.request).then(function (cached) {
                    return cached || caches.match('/');
                });
            })
        );
        return;
    }

    // Default: network first
    e.respondWith(
        fetch(e.request).catch(function () {
            return caches.match(e.request);
        })
    );
});
