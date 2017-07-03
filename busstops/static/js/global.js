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
