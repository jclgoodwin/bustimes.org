/*jslint browser: true*/

if (navigator.serviceWorker && location.protocol === 'https:') {
    window.addEventListener('load', function() {
        if (navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage({'command': 'trimCaches'});
        } else {
            navigator.serviceWorker.register('/serviceworker.js', {
                scope: '/'
            }).catch(function() {
                // never mind
            });
        }
    });
}

(function () {
    var cookieMessage = document.getElementById('cookie-message');
    if (cookieMessage && document.cookie.indexOf('seen_cookie_message=yes') === -1) {
        cookieMessage.style.display = 'block';
        document.cookie = 'seen_cookie_message=yes; max-age=31536000; path=/';
    }

    var ads = document.getElementsByClassName('banner-ad');
    window.adsbygoogle = (window.adsbygoogle || []);
    window.adsbygoogle.requestNonPersonalizedAds = 1;

    if (window.IntersectionObserver) {
        var observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting && !entry.target.querySelector('.adsbygoogle').innerHTML) {
                    var script = document.createElement('script');
                    script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
                    window.adsbygoogle.push({});
                    document.body.appendChild(script);
                }
            });
        });
    }

    for (var i = ads.length - 1; i >= 0; i -= 1) {
        if (observer) {
            observer.observe(ads[i]);
        } else {
            window.adsbygoogle.push({});
        }
    }

    if (!observer) {
        var script = document.createElement('script');
        script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
        document.body.appendChild(script);
    }
})();
