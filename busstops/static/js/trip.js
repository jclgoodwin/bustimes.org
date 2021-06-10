(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest
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

    var loadVehiclesTimeout;

    function loadVehicles() {
        if (!window.SERVICE) {
            return;
        }
        var params = '?service=' + window.SERVICE;
        reqwest(
            '/vehicles.json' + params,
            function(data) {
                if (data) {
                    window.bustimes.handleVehicles(data);
                }
                if (map && data.length) {
                    loadVehiclesTimeout = setTimeout(loadVehicles, 10000);
                }
            }
        );
    }

    function handleVisibilityChange(event) {
        if (event.target.hidden) {
            if (loadVehiclesTimeout) {
                clearTimeout(loadVehiclesTimeout);
            }
        } else {
            loadVehicles();
        }
    }

    if (window.STOPS) {
        var map = L.map('map');

        window.bustimes.doTileLayer(map);

        window.bustimes.map = map;

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

        loadVehicles();

        if (document.addEventListener) {
            document.addEventListener('visibilitychange', handleVisibilityChange);
        }

        L.control.locate().addTo(map);
    }
})();
