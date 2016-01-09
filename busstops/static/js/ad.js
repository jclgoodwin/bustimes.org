(function () {
    var width = window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth;

    if (width >= 768) {
        var random = Math.floor(Math.random() * 3);

        if (random === 0) {
            document.getElementById('ad').innerHTML = '<a href="https://www.awin1.com/cread.php?s=178399&v=2678&q=97593&r=242611"><img src="https://www.awin1.com/cshow.php?s=178399&v=2678&q=97593&r=242611"></a>';
            return;
        }
    }
    var script = document.createElement('script');
    script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
    document.body.appendChild(script);
    document.getElementById('ad').innerHTML = '<ins class="adsbygoogle" data-ad-client="ca-pub-4420219114164200" data-ad-slot="5070920457" data-ad-format="auto"></ins>';
    (adsbygoogle = window.adsbygoogle || []).push({});
})();
