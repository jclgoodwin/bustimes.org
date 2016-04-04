/*jslint browser: true*/

/*
 * Front page things
 */
(function () {
    'use strict';

    /*
     * SVG map
     */
    function highlight(href, add) {
        var i,
            regionShapeLinks = document.getElementById('svgmap').getElementsByTagName('a');

        for (i = regionShapeLinks.length - 1; i >= 0; i -= 1) {
            if ('/regions/GB' === href || regionShapeLinks[i].getAttributeNS('http://www.w3.org/1999/xlink', 'href') === href) {
                if (add) {
                    regionShapeLinks[i].setAttribute('class', 'highlight');
                } else {
                    regionShapeLinks[i].setAttribute('class', '');
                }
            }
        }
    }

    function handleMouseOver() {
        highlight(this.getAttribute('href'), true);
    }

    function handleMouseOut() {
        highlight(this.getAttribute('href'), false);
    }

    var i,
        regionNameLinks = document.getElementById('regions').getElementsByTagName('a');

    for (i = regionNameLinks.length - 1; i >= 0; i -= 1) {
        regionNameLinks[i].onmouseover = regionNameLinks[i].onfocus = handleMouseOver;
        regionNameLinks[i].onmouseout = regionNameLinks[i].onblur = handleMouseOut;
    }

    /*
     * 'Search places' form
     */
    document.getElementById('search').outerHTML += '<ul id="search-results"></ul>';
    document.getElementById('search').onkeydown = debounce(250, function () {
        var i,
            resultsElement = document.getElementById('search-results'),
            value = String.prototype.trim ? this.value.trim() : this.value;

        if (value === '') {
            resultsElement.innerHTML = '';
        } else {
            reqwest('/search.json?q=' + value, function (res) {
                var output = '';
                for (i = 0; i < res.length; i += 1) {
                    output += '<li><a href="' + res[i].url + '">' + res[i].name + '</a></a>';
                }
                resultsElement.innerHTML = output;
            });
        }
    });

})();
