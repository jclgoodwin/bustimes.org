/*jslint browser: true*/

(function () {
    'use strict';

    var ad = document.getElementById('ad');

    if (ad.clientWidth >= 768) {
        var random =  Math.random();
        if (random < .4) {
            postscribe('#ad', '<script src="https://go2.adversal.com/ttj?id=7046027&size=728x90&promo_sizes=468x60,320x50,300x50,216x36"><\/script>');
            return;
        } else if (random < .6) {
            window.amazon_ad_tag = 'joshgood-21&internal=1';
            window.amazon_ad_width = '728';
            window.amazon_ad_height = '90';
            postscribe('#ad', '<script type="text/javascript" src="https://ir-uk.amazon-adsystem.com/s/ads.js"><\/script>');
            return;
        }
    }
    var script = document.createElement('script');
    (window.adsbygoogle = window.adsbygoogle || []).push({});
    script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
    ad.innerHTML = '<ins class="adsbygoogle" data-ad-client="ca-pub-4420219114164200" data-ad-slot="5070920457" data-ad-format="auto"></ins>';
    ad.appendChild(script);
})();
