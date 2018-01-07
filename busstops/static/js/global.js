/*jslint browser: true*/

if (navigator.serviceWorker && location.host !== 'localhost:8000') {
    navigator.serviceWorker.register('/serviceworker.js', {
        scope: '/'
    });
    window.addEventListener('load', function () {
        if (navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage({'command': 'trimCaches'});
        }
    });
}

if (window.adsbygoogle && document.documentElement.clientWidth >= 1280) {
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://sac.ayads.co/sublime/21256';
    document.documentElement.appendChild(s);
}
