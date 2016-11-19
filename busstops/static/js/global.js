/*jslint browser: true*/

if (navigator.serviceWorker && location.host !== 'localhost:8000') {
    navigator.serviceWorker.register('/serviceworker.js', {
        scope: '/'
    });
    window.addEventListener('load', function() {
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

        if (ad.clientWidth >= 768) {
            random = Math.random();
            if (random < .5) {
                if (window.CHITIKA === undefined) {
                    window.CHITIKA = {units: []};
                }
                window.CHITIKA.units.push({
                    calltype: 'async[2]',
                    publisher: 'jgoodwin',
                    width: 728,
                    height: 90,
                    sid: 'Chitika Default'
                });
                ad.innerHTML = '<div id="chitikaAdBlock-0"></div>';
                script.src = 'https://cdn.chitika.net/getads.js';
                ad.appendChild(script)
                return;
            }
        }

        (window.adsbygoogle = window.adsbygoogle || []).push({});
        script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
        ad.innerHTML = '<ins class="adsbygoogle" data-ad-client="ca-pub-4420219114164200" data-ad-slot="5070920457" data-ad-format="auto"></ins>';
        ad.appendChild(script);
    }
})();
