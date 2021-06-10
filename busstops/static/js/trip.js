(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L
    */

    if (document.referrer.indexOf('/stops/') > -1) {
        var links = document.querySelectorAll('.trip-timetable a');
        links.forEach(function(link) {
            // debugger;
            if (link.href === document.referrer) {
                link.parentNode.parentNode.classList.add('referrer');
            }
        });
    }

    if (window.STOPS) {
        var map = L.map('trip-map');

        window.bustimes.doTileLayer(map);

        var bounds = L.latLngBounds();

        window.STOPS.forEach(function(stop) {
            var location = L.GeoJSON.coordsToLatLng(stop.latlong);

            if (stop.bearing !== null) {
                var html = '<div class="stop-arrow" style="' + window.bustimes.getTransform(stop.bearing + 45) + '"></div>';
            } else {
                html = '<div class="stop-arrow no-direction"></div>';
            }

            L.marker(location, {
                icon: L.divIcon({
                    iconSize: [9, 9],
                    html: html,
                    className: 'stop'
                })
            }).bindTooltip(stop.time).addTo(map);

            bounds.extend(location);
        });

        map.fitBounds(bounds);

        map.setMaxBounds(bounds);

        L.control.locate().addTo(map);
    }
})();
