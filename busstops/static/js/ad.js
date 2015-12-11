(function () {
    var container = document.getElementById('ad'),
        ads = [
            function (container) {
                var ins = document.createElement('ins'),
                    script = document.createElement('script');
                ins.className = 'adsbygoogle';
                ins.setAttribute('data-ad-client', 'ca-pub-4420219114164200');
                ins.setAttribute('data-ad-slot', '5070920457');
                ins.setAttribute('data-ad-format', 'auto');
                script.src = '//pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
                container.appendChild(ins).appendChild(script);
                (adsbygoogle = window.adsbygoogle || []).push({});
            },
            function (container) {
                postscribe(container, '<script src="https://go2.adversal.com/ttj?id=5940208&size=728x90&promo_sizes=468x60,320x50,300x50,216x36"></script>');
            }
        ],
        i = Math.floor(Math.random() * ads.length);

    ads[i](container);
})();
