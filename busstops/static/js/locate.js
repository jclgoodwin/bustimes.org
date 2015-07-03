(function () {

    var buttons = document.getElementsByTagName('button');

    buttons[0].onclick = function() {
        if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(function (p) {
                    var x = Math.round(p.coords.longitude * 1000 ) / 1000,
                        y = Math.round(p.coords.latitude * 1000 ) / 1000;
                    buttons[0].className += ' loading';
                    buttons[0].setAttribute('disabled', 'disabled')
                    buttons[0].innerHTML = 'Finding bus stops near ' + y + ', ' + x + '\u2026';
                    window.location.href = '/coordinates/' + y + ',' + x;
                });
        }
    }

    var regionNameLinks = document.getElementsByTagName('ul')[0].getElementsByTagName('a');

    function highlight(href, add) {
        var regionShapeLinks = document.getElementsByTagName('svg')[0].getElementsByTagName('a');
        for (var i = 0; i < regionShapeLinks.length; i++) {
            if ('/regions/GB' === href || regionShapeLinks[i].getAttributeNS('http://www.w3.org/1999/xlink', 'href') === href) {
                if (add) {
                    regionShapeLinks[i].classList.add('highlight');
                } else {
                    regionShapeLinks[i].classList.remove('highlight');
                }
            }
        }
    }

    for (var i = 0; i < regionNameLinks.length; i++) {
        regionNameLinks[i].onmouseover = function(e) {
            highlight(this.getAttribute('href'), true);
        };
        regionNameLinks[i].onmouseout = function(e) {
            highlight(this.getAttribute('href'), false);
        };
    }

})();
