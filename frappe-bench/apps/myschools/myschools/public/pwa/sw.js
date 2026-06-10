/* MY School portal service worker — cache static assets, offline shell for portal pages. */
const CACHE = "mys-portal-v1";
const OFFLINE_URL = "/assets/myschools/pwa/offline.html";
const PRECACHE = [
	"/assets/myschools/css/myschools.css",
	"/assets/myschools/images/mys-logo.svg",
	"/assets/myschools/images/mys-favicon.svg",
	"/assets/myschools/pwa/manifest.json",
	"/assets/myschools/js/portal_pwa.js",
	OFFLINE_URL,
];

const PORTAL_PREFIXES = ["/guardian", "/teacher", "/branch", "/inspection", "/portal"];

self.addEventListener("install", (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) => cache.addAll(PRECACHE))
			.then(() => self.skipWaiting())
	);
});

self.addEventListener("activate", (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) =>
				Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
			)
			.then(() => self.clients.claim())
	);
});

function isPortalNavigation(url) {
	return PORTAL_PREFIXES.some(
		(prefix) => url.pathname === prefix || url.pathname.startsWith(prefix + "/")
	);
}

function isStaticAsset(url) {
	return url.pathname.startsWith("/assets/myschools/") || PRECACHE.includes(url.pathname);
}

self.addEventListener("fetch", (event) => {
	if (event.request.method !== "GET") {
		return;
	}
	const url = new URL(event.request.url);
	if (url.origin !== self.location.origin) {
		return;
	}

	if (isStaticAsset(url)) {
		event.respondWith(
			caches.match(event.request).then((cached) => cached || fetch(event.request))
		);
		return;
	}

	if (isPortalNavigation(url)) {
		event.respondWith(
			fetch(event.request).catch(() =>
				caches
					.match(OFFLINE_URL)
					.then((offline) => offline || new Response("Offline", { status: 503 }))
			)
		);
	}
});
