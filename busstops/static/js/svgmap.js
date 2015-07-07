(function () {
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

    var regionNameLinks = document.getElementsByTagName('ul')[0].getElementsByTagName('a');

    for (var i = 0; i < regionNameLinks.length; i++) {
        regionNameLinks[i].onmouseover = regionNameLinks[i].onfocus = function(e) {
            highlight(this.getAttribute('href'), true);
        };
        regionNameLinks[i].onmouseout = regionNameLinks[i].onblur = function(e) {
            highlight(this.getAttribute('href'), false);
        };
    }
})();
