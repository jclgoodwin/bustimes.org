(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L
    */

    var tiles = 'https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png';
    var attribution = '<a href="https://stadiamaps.com/">© Stadia Maps</a> <a href="https://openmaptiles.org/">© OpenMapTiles</a> <a href="https://www.openstreetmap.org/about/">© OpenStreetMap contributors</a>';

    function getTransform(heading, scale) {
        if (heading === null && !scale) {
            return '';
        }
        var transform = 'transform:';
        if (heading !== null) {
            transform += ' rotate(' + heading + 'deg)';
        }
        if (scale) {
            transform += ' scale(1.5)';
        }
        return '-webkit-' + transform + ';' + transform + ';';
    }

    function getBusIcon(item, active) {
        var heading = item.h;
        if (heading !== null) {
            var arrow = '<div class="arrow" style="' + getTransform(heading, active) + '"></div>';
            if (heading < 180) {
                heading -= 90;
            } else {
                heading -= 270;
            }
        }
        var className = 'bus';
        if (active) {
            className += ' selected';
        }
        var style = getTransform(heading, active);
        if (item.c) {
            if (typeof(item.c) == 'number') {
                className += ' livery-' + item.c;
            } else {
                style += 'background:' + item.c;
                if (item.t) {
                    className += ' white-text';
                }
            }
        }
        var html = '<div class="' + className + '" style="' + style + '">';
        if (item.r) {
            html += item.r;
        }
        html += '</div>';
        if (arrow) {
            html += arrow;
        }
        return L.divIcon({
            iconSize: [20, 20],
            html: html,
            popupAnchor: [0, -5],
        });
    }

    function getDelay(item) {
        if (item.e === 0) {
            return 'On time<br>';
        }
        if (item.e) {
            var content = 'About ';
            if (item.e > 0) {
                content += item.e;
            } else {
                content += item.e * -1;
            }
            content += ' minute';
            if (item.e !== 1 && item.e !== -1) {
                content += 's';
            }
            if (item.e > 0) {
                content += ' early';
            } else {
                content += ' late';
            }
            content += '<br>';
            return content;
        }
        return '';
    }

    window.bustimes = {
        doTileLayer: function(map) {
            map.attributionControl.setPrefix('');
            L.tileLayer(tiles, {
                attribution: attribution
            }).addTo(map);
        },

        getDelay: getDelay,

        getPopupContent: function(item) {
            var delta = getDelay(item);

            var datetime = new Date(item.d);

            return delta + 'Updated at ' + datetime.toTimeString().slice(0, 5);
        },

        getBusIcon: getBusIcon,
        getTransform: getTransform,
    };
})();
