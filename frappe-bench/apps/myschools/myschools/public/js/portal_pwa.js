/* Register the MY School portal service worker on authenticated portal pages. */
(function () {
	if (!("serviceWorker" in navigator)) {
		return;
	}

	var path = window.location.pathname || "";
	var portalPrefixes = ["/guardian", "/teacher", "/branch", "/inspection", "/portal"];
	var onPortal = portalPrefixes.some(function (prefix) {
		return path === prefix || path.indexOf(prefix + "/") === 0;
	});
	if (!onPortal) {
		return;
	}

	window.addEventListener("load", function () {
		navigator.serviceWorker
			.register("/mys-pwa-sw.js", { scope: "/" })
			.catch(function () {
				/* Non-fatal — portal still works without SW */
			});
	});
})();
