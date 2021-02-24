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
        var className = 'bus';
        if (active) {
            className += ' selected';
        }
        var heading = item.heading;
        if (heading !== null) {
            var arrow = '<div class="arrow" style="' + getTransform(heading, active) + '"></div>';
            if (heading < 180) {
                className += ' right';
                heading -= 90;
            } else {
                heading -= 270;
            }
        }
        var style = getTransform(heading, active);
        if (item.vehicle.livery) {
            className += ' livery-' + item.vehicle.livery;
        } else if (item.vehicle.css) {
            style += 'background:' + item.vehicle.css;
            if (item.vehicle.text_colour) {
                className += ' white-text';
            }
        }
        var html = '<div class="' + className + '" style="' + style + '">';
        if (item.service) {
            html += item.service.line_name;
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

    var agoTimeout;

    function getPopupContent(item) {
        var now = new Date();
        var then = new Date(item.datetime);
        var ago = Math.round((now.getTime() - then.getTime()) / 1000);

        if (item.service) {
            var content = item.service.line_name;
            if (item.destination) {
                content += ' to ' + item.destination;
            }
            if (item.service.url) {
                content = '<a href="' + item.service.url + '">' + content + '</a>';
            }
        } else {
            content = '';
        }

        content += '<a href="' + item.vehicle.url + '">' + item.vehicle.name + '</a>';

        if (item.vehicle.features) {
            content += item.vehicle.features + '<br>';
        }

        if (item.occupancy) {
            content += item.occupancy + '<br>';
        }

        if (ago >= 1800) {
            content += 'Updated at ' + then.toTimeString().slice(0, 8);
        } else {
            content += '<time datetime="' + item.datetime + '" title="' + then.toTimeString().slice(0, 8) + '">';
            if (ago >= 59) {
                var minutes = Math.round(ago / 60);
                if (minutes === 1) {
                    content += '1 minute';
                } else {
                    content += minutes + ' minutes';
                }
                agoTimeout = setTimeout(updatePopupContent, (61 - ago % 60) * 1000);
            } else {
                if (ago === 1) {
                    content += '1 second';
                } else {
                    content += ago + ' seconds';
                }
                agoTimeout = setTimeout(updatePopupContent, 1000);
            }
            content += ' ago</time>';
        }
        return content;
    }

    function updatePopupContent() {
        if (agoTimeout) {
            clearTimeout(agoTimeout);
        }
        var marker = window.bustimes.vehicleMarkers[window.bustimes.clickedMarker];
        if (marker) {
            var item = marker.options.item;
            marker.getPopup().setContent(getPopupContent(item));
        }
    }

    window.bustimes = {
        doTileLayer: function(map) {
            map.attributionControl.setPrefix('');
            L.tileLayer(tiles, {
                attribution: attribution
            }).addTo(map);
        },

        getPopupContent: getPopupContent,

        updatePopupContent: updatePopupContent,

        getBusIcon: getBusIcon,

        getTransform: getTransform,

        vehicleMarkers: {},
    };
})();
