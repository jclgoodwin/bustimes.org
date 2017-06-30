/*jslint browser: true*/

if (navigator.serviceWorker && location.host !== 'localhost:8000') {
    navigator.serviceWorker.register('/serviceworker.js', {
        scope: '/'
    });
    window.addEventListener('load', function () {
        'use strict';

        if (navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage({'command': 'trimCaches'});
        }
    });
}

(function () {
    'use strict';

    var ad = document.getElementById('ad'),
        script,
        random;

    if (!ad.innerHTML.trim()) {
        script = document.createElement('script');

        if (ad.clientWidth >= 768 && Math.random() > 0.3) {
            postscribe('https://ap.lijit.com/www/delivery/fpi.js?z=440001&width=728&height=90');
        } else {
            (window.adsbygoogle = window.adsbygoogle || []).push({});
            script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
            ad.innerHTML = '<ins class="adsbygoogle" data-ad-client="ca-pub-4420219114164200" data-ad-slot="5070920457" data-ad-format="auto"></ins>';
            ad.appendChild(script);
        }
    }
}());
