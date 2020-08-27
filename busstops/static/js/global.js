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
    try {
        if (localStorage && localStorage.hideAds) {
            return;
        }
    } catch (error) {
        // never mind
    }

    var ads = document.getElementsByClassName('adsbygoogle');
    if (!ads.length) {
        return;
    }

    if (document.cookie.indexOf('seen_cookie_message=') === -1 && document.cookie.indexOf('personalise_ads=') === -1) {
        var cookieDiv = document.getElementById('cookie-message');
        cookieDiv.innerHTML = '<p>Can we show you personalised advertisements, using <a href="/cookies">cookies</a>?</p>';

        var ok = document.createElement('button');
        ok.innerHTML = 'OK';
        ok.onclick = function() {
            document.body.removeChild(cookieDiv);
        };

        var yes = document.createElement('button');
        yes.innerHTML = 'Yes please';
        yes.onclick = function() {
            cookieDiv.innerHTML = '<p>Great. If you change your mind you can use <a href="/cookies">change your settings</a>.</p>';
            cookieDiv.appendChild(ok);
            document.cookie = 'personalise_ads=yes; max-age=31536000; path=/';
        };
        cookieDiv.appendChild(yes);

        var no = document.createElement('button');
        no.innerHTML = 'No thanks';
        no.onclick = function() {
            cookieDiv.innerHTML = '<p>Fair enough. You may see ads that are less relevant to you. These ads use <a href="/cookies">cookies</a>, but not for personalization./p>';
            cookieDiv.appendChild(ok);
        };
        cookieDiv.appendChild(no);

        cookieDiv.style.display = 'block';

        document.cookie = 'personalise_ads=no; max-age=31536000; path=/';
    }

    window.adsbygoogle = (window.adsbygoogle || []);
    if (document.cookie.indexOf('personalise_ads=yes') === -1) {
        window.adsbygoogle.requestNonPersonalizedAds = 1;
    }
    var script = document.createElement('script');
    script.dataset.adClient = 'ca-pub-4420219114164200';
    script.async = 'async';
    script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
    document.body.appendChild(script);

    for (var i = ads.length - 1; i >= 0; i -= 1) {
        window.adsbygoogle.push({});
    }
})();
