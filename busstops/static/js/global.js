/*jslint browser: true*/

(function () {

    var fareTables = document.getElementById('fare-tables');
    if (fareTables) {
        fareTables.onchange = function(event) {
            if (event.target.value) {
                var container = document.getElementById('fare-table');
                container.className = 'loading';
                reqwest('/fares/tables/' + event.target.value, function(data) {
                    container.innerHTML = data;
                    container.className = '';
                });
            }
        };
    }

    var ads = document.getElementsByClassName('adsbygoogle');
    if (!ads.length) {
        return;
    }

    try {
        if (localStorage && localStorage.hideAds) {
            return;
        }
    } catch (error) {
        // never mind
    }

    window.adsbygoogle = (window.adsbygoogle || []);
    window.adsbygoogle.requestNonPersonalizedAds = 1;

    var script = document.createElement('script');
    script.dataset.adClient = 'ca-pub-4420219114164200';
    script.async = 'async';
    script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
    document.body.appendChild(script);

    for (var i = ads.length - 1; i >= 0; i -= 1) {
        window.adsbygoogle.push({});
    }
})();
