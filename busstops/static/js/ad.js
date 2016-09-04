/*jslint browser: true*/

(function () {
    'use strict';

    var ad = document.getElementById('ad');

    if (ad.clientWidth >= 768) {
        var random =  Math.random();
        if (random < .5) {
            window.adtomation={id:'9400117',size:'728x90'};
            postscribe('#ad', '<div class="adtomation"><script src="//bid.adtomation.com/js/engine.js"><\/script></div>');
            return;
        }
    }
    var script = document.createElement('script');
    (window.adsbygoogle = window.adsbygoogle || []).push({});
    script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
    ad.innerHTML = '<ins class="adsbygoogle" data-ad-client="ca-pub-4420219114164200" data-ad-slot="5070920457" data-ad-format="auto"></ins>';
    ad.appendChild(script);
})();

