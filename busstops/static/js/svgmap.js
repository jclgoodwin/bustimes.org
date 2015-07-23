/*
 * jQuery throttle / debounce - v1.1 - 3/7/2010
 * http://benalman.com/projects/jquery-throttle-debounce-plugin/
 * 
 * Copyright (c) 2010 "Cowboy" Ben Alman
 * Dual licensed under the MIT and GPL licenses.
 * http://benalman.com/about/license/
 */
(function(b,c){var $=b.jQuery||b.Cowboy||(b.Cowboy={}),a;$.throttle=a=function(e,f,j,i){var h,d=0;if(typeof f!=="boolean"){i=j;j=f;f=c}function g(){var o=this,m=+new Date()-d,n=arguments;function l(){d=+new Date();j.apply(o,n)}function k(){h=c}if(i&&!h){l()}h&&clearTimeout(h);if(i===c&&m>e){l()}else{if(f!==true){h=setTimeout(i?k:l,i===c?e-m:e)}}}if($.guid){g.guid=j.guid=j.guid||$.guid++}return g};$.debounce=function(d,e,f){return f===c?a(d,e,false):a(d,f,e!==false)}})(this);


/*
 * Front page things
 */
(function () {

    /*
     * SVG map
     */
    function highlight(href, add) {
        var regionShapeLinks = document.getElementById('svgmap').getElementsByTagName('a');
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

    var regionNameLinks = document.getElementById('regions').getElementsByTagName('a');

    for (var i = 0; i < regionNameLinks.length; i++) {
        regionNameLinks[i].onmouseover = regionNameLinks[i].onfocus = function(e) {
            highlight(this.getAttribute('href'), true);
        };
        regionNameLinks[i].onmouseout = regionNameLinks[i].onblur = function(e) {
            highlight(this.getAttribute('href'), false);
        };
    }

    /*
     * 'Search places' form
     */
    $(document.getElementById('q')).on('keypress', $.debounce(250, function (e) {
        var resultsElement = document.getElementById('results');
        if (this.value === '') {
            resultsElement.innerHTML = '';
        } else {
            $.get('/search.json', {
                q: this.value,
            }, function(data) {
                var output = '';
                for (var i = 0; i < data.length; i++) {
                    output += '<li><a href="' + data[i].url + '">' + data[i].name + '</a></a>';
                }
                resultsElement.innerHTML = output;
            }, 'json');
        }
    }));
    $(document.getElementById('search')).on('submit', function (e) {
        e.preventDefault();
    });

})();
