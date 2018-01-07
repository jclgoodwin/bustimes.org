'use strict';

const version = '0002';
const pagesCacheName = version + 'pages';
const staticCacheName = version + 'static';


function updateStaticCache() {
    return caches.open(staticCacheName).then(cache => {
        // These items must be cached for the Service Worker to complete installation
        return cache.addAll([
            '/offline',
            '/',
        ]);
    });
}

// Stash a response in a specified cache, using the request as a key
function stashInCache(cacheName, request, response) {
    caches.open(cacheName).then(cache => {
        cache.put(request, response);
    });
}

// Recursively limit the number of items in a specified cache
function trimCache(cacheName, maxItems) {
    caches.open(cacheName).then(cache => {
        cache.keys().then(keys => {
            if (keys.length > maxItems) {
                cache.delete(keys[0]).then(trimCache(cacheName, maxItems));
            }
        });
    });
}

// Remove caches whose name is no longer valid
function clearOldCaches() {
    return caches.keys().then(keys => {
        return Promise.all(keys.filter(key => {
            return key.indexOf(version) !== 0;
        }).map(caches.delete));
    });
}

self.addEventListener('install', event => {
    event.waitUntil(
        updateStaticCache().then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        clearOldCaches().then(() => self.clients.claim())
    );
});

self.addEventListener('message', event => {
    if (event.data.command === 'trimCaches') {
        trimCache(pagesCacheName, 50);
        trimCache(staticCacheName, 50);
    }
});

self.addEventListener('fetch', event => {
    let request = event.request;
    let url = new URL(request.url);

    if (url.origin !== location.origin) {
        return;
    }

    // For non-GET requests, try the network first, fall back to the offline page
    if (request.method !== 'GET') {
        event.respondWith(
            fetch(request).catch(() => caches.match('/offline'))
        );
        return;
    }

    // For HTML requests, try the network first, fall back to the cache, finally the offline page
    if (request.headers.get('Accept').includes('text/html')) {
        event.respondWith(
            fetch(request)
                .then(response => {
                    // NETWORK
                    // Stash a copy of this page in the pages cache
                    let copy = response.clone();
                    stashInCache(pagesCacheName, request, copy);
                    return response;
                })
                .catch(() => {
                    // CACHE or FALLBACK
                    return caches.match(request).then(response => response || caches.match('/offline'));
                })
        );
        return;
    }

    // For non-HTML requests, look in the cache first, fall back to the network
    event.respondWith(
        caches.match(request).then(response => response || fetch(request).then(response => {
            // If the request is for a static file, stash a copy of this image in the static file cache
            if (request.url.includes('/static/css/') || request.url.includes('/static/js/')) {
                let copy = response.clone();
                stashInCache(staticCacheName, request, copy);
            }
            return response;
        }))
    );
});
