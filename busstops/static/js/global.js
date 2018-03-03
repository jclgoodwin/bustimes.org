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

if (window.adsbygoogle) {
    var clientWidth = document.documentElement.clientWidth;
    if (clientWidth >= 1080 || (clientWidth < 768 && window.location.href.indexOf('/services/') === -1)) {
        var s = document.createElement('script');
        s.async = true;
        s.src = 'https://sac.ayads.co/sublime/21256';
        document.documentElement.appendChild(s);
    } else {
        window.adsbygoogle.push({
            google_ad_client: 'ca-pub-4420219114164200',
            enable_page_level_ads: true
        });
    }
}
