/*jslint browser: true*/

(function () {
    'use strict';

    var ad = document.getElementById('ad'),
        script;

    if (ad && !ad.innerHTML.trim()) {

        if (ad.clientWidth >= 768) {
            window.medianet_width = "728";
            window.medianet_height = "90";
            window.medianet_crid = "554393111";
            window.medianet_versionId = "3111299";
            window.postscribe(ad, '<script src="//contextual.media.net/nmedianet.js?cid=8CUDT4GNF"></script>');
        } else {
            script = document.createElement('script');
            (window.adsbygoogle = window.adsbygoogle || []).push({});
            script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
            ad.innerHTML = '<ins class="adsbygoogle" data-ad-client="ca-pub-4420219114164200" data-ad-slot="5070920457" data-ad-format="auto"></ins>';
            ad.appendChild(script);
        }
    }
}());

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
