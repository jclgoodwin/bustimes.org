/*jslint browser: true*/

if (navigator.serviceWorker && location.host !== 'localhost:8000') {
    try {
        navigator.serviceWorker.register('/serviceworker.js', {
            scope: '/'
        });
    } catch (ignore) {
        // never mind
    }
    window.addEventListener('load', function () {
        if (navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage({'command': 'trimCaches'});
        }
    });
}

(function () {
    var cookieMessage = document.getElementById('cookie-message');
    if (cookieMessage && document.cookie.indexOf('seen_cookie_message=yes') === -1) {
        cookieMessage.style.display = 'block';
        document.cookie = 'seen_cookie_message=yes; max-age=31536000; path=/';
    }
})();
