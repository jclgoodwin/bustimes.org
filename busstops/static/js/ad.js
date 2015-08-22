(function () {
    'use strict';

    var width = window.innerWidth || document.documentElement.offsetWidth || document.body.offsetWidth,
        ads,
        i,
        ad;

    if (width > 768) {
        ads = [
            '<a href="https://www.awin1.com/cread.php?s=494905&v=6108&q=240111&r=242611"><img src="https://www.awin1.com/cshow.php?s=494905&v=6108&q=240111&r=242611" alt="Pact Coffee" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=494909&v=6108&q=240111&r=242611"><img src="https://www.awin1.com/cshow.php?s=494909&v=6108&q=240111&r=242611" alt="Pact Coffee" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=192825&v=2829&q=102097&r=242611"><img src="https://www.awin1.com/cshow.php?s=192825&v=2829&q=102097&r=242611" alt="First TransPennine Express" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=494903&v=6108&q=240109&r=242611"><img src="https://www.awin1.com/cshow.php?s=494903&v=6108&q=240109&r=242611" alt="Pact Coffee" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=516805&v=6108&q=251949&r=242611"><img src="https://www.awin1.com/cshow.php?s=516805&v=6108&q=251949&r=242611" alt="Pact Coffee" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=447163&v=5667&q=215439&r=242611"><img src="https://www.awin1.com/cshow.php?s=447163&v=5667&q=215439&r=242611" alt="Voyages Sncf" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=192820&v=2829&q=102095&r=242611"><img src="https://www.awin1.com/cshow.php?s=192820&v=2829&q=102095&r=242611" alt="First TransPennine Express" /></a>',
        ];
    } else if (width > 488) {
        ads = [
            '<a href="https://www.awin1.com/cread.php?s=194217&v=2829&q=102562&r=242611"><img src="https://www.awin1.com/cshow.php?s=194217&v=2829&q=102562&r=242611" alt="First TransPennine Express" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=192827&v=2829&q=102098&r=242611"><img src="https://www.awin1.com/cshow.php?s=192827&v=2829&q=102098&r=242611" alt="First TransPennine Express" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=194216&v=2829&q=102560&r=242611"><img src="https://www.awin1.com/cshow.php?s=194216&v=2829&q=102560&r=242611" alt="First TransPennine Express" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=192834&v=2829&q=102100&r=242611"><img src="https://www.awin1.com/cshow.php?s=192834&v=2829&q=102100&r=242611" alt="First TransPennine Express" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=494899&v=6108&q=240103&r=242611"><img src="https://www.awin1.com/cshow.php?s=494899&v=6108&q=240103&r=242611" alt="Pact Coffee" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=494897&v=6108&q=240105&r=242611"><img src="https://www.awin1.com/cshow.php?s=494897&v=6108&q=240105&r=242611" alt="Pact Coffee" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=494927&v=6108&q=240117&r=242611"><img src="https://www.awin1.com/cshow.php?s=494927&v=6108&q=240117&r=242611" alt="Pact Coffee" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=447173&v=5667&q=215449&r=242611"><img src="https://www.awin1.com/cshow.php?s=447173&v=5667&q=215449&r=242611" alt="Voyages Sncf" /></a>',
        ];
    } else {
        ads = [
            '<a href="https://www.awin1.com/cread.php?s=495357&v=6108&q=240297&r=242611"><img src="https://www.awin1.com/cshow.php?s=495357&v=6108&q=240297&r=242611" alt="Pact Coffee" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=494927&v=6108&q=240117&r=242611"><img src="https://www.awin1.com/cshow.php?s=494927&v=6108&q=240117&r=242611" alt="Pact Coffee" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=494923&v=6108&q=240117&r=242611"><img src="https://www.awin1.com/cshow.php?s=494923&v=6108&q=240117&r=242611" alt="Pact Coffee" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=194216&v=2829&q=102560&r=242611"><img src="https://www.awin1.com/cshow.php?s=194216&v=2829&q=102560&r=242611" alt="First TransPennine Express" /></a>',
            '<a href="https://www.awin1.com/cread.php?s=447173&v=5667&q=215449&r=242611"><img src="https://www.awin1.com/cshow.php?s=447173&v=5667&q=215449&r=242611" alt="Voyages Sncf" /></a>',
        ];
    }

    ad = ads[Math.floor(Math.random() * ads.length)];
    document.getElementById('ad').innerHTML += ad;
}());
