(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest
    */

    var map;

    function getMarker(latLng, direction) {
        direction = (direction || 0) - 135;
        return L.marker(latLng, {
            icon: L.divIcon({
                iconSize: [16, 16],
                html: '<div class="arrow" style="-ms-transform: rotate(' + direction + 'deg);-webkit-transform: rotate(' + direction + 'deg);-moz-transform: rotate(' + direction + 'deg);-o-transform: rotate(' + direction + 'deg);transform: rotate(' + direction + 'deg)"></div>',
                className: 'just-arrow'
            })
        });
    }

    var timeMarkerOptions = {
        radius: 3,
        fillColor: '#000',
        fillOpacity: 1,
        weight: 0,
        interactive: false
    };

    function closeMap() {
        window.location.hash = '';
        return false;
    }

    window.onkeydown = function(event) {
        if (event.keyCode === 27) { // esc
            closeMap();
        }
    };

    window.onhashchange = function(event) {
        if (map) {
            map.remove();
            map = null;
        }
        maybeOpenMap();
        event.preventDefault();
        return false;
    };

    function maybeOpenMap() {
        var journey = window.location.hash.slice(1),
            element = document.getElementById(journey);

        if (!element) {
            return;
        }

        reqwest('/' + journey + '.json', function(locations) {

            var mapContainer = element.getElementsByClassName('map')[0],
                layerGroup = L.layerGroup();

            map =  L.map(mapContainer);

            layerGroup.addTo(map);

            map.attributionControl.setPrefix('');

            L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', {
                attribution: '<a href="https://stadiamaps.com/">© Stadia Maps</a> <a href="https://openmaptiles.org/">© OpenMapTiles</a> <a href="https://www.openstreetmap.org/about/">© OpenStreetMap contributors</a>',
            }).addTo(map);

            var j,
                dateTime,
                popup,
                delta,
                coordinates,
                line = [],
                bounds,
                latDistance,
                lngDistance,
                timeDistance,
                previousCoordinates,
                minutes,
                previousTimestamp,
                latSpeed,
                lngSpeed;


            for (var i = locations.length - 1; i >= 0; i -= 1) {
                dateTime = new Date(locations[i].datetime);
                popup = dateTime.toTimeString().slice(0, 8);
                delta = locations[i].delta;
                if (delta) {
                    popup += '<br>About ';
                    if (delta > 0) {
                        popup += delta;
                    } else {
                        popup += delta * -1;
                    }
                    popup += ' minute';
                    if (delta !== 1 && delta !== -1) {
                        popup += 's';
                    }
                    if (delta > 0) {
                        popup += ' early';
                    } else {
                        popup += ' late';
                    }
                } else if (delta === 0) {
                    popup += '<br>On time';
                }
                coordinates = L.latLng(locations[i].coordinates[1], locations[i].coordinates[0]);
                getMarker(coordinates, locations[i].direction).bindTooltip(popup).addTo(layerGroup);

                if (previousCoordinates) {
                    latDistance = previousCoordinates.lat - coordinates.lat;
                    lngDistance = previousCoordinates.lng - coordinates.lng;
                    minutes = Math.floor(previousTimestamp / 60000) * 60000;
                    timeDistance = previousTimestamp - dateTime.getTime();
                    if (timeDistance) {
                        latSpeed = latDistance / timeDistance;
                        lngSpeed = lngDistance / timeDistance;

                        for (j = previousTimestamp - minutes; j <= timeDistance; j += 60000) {
                            L.circleMarker(L.latLng(
                                previousCoordinates.lat - latSpeed * j,
                                previousCoordinates.lng - lngSpeed * j
                            ), timeMarkerOptions).addTo(layerGroup);
                        }
                    }
                }
                line.push(coordinates);
                previousTimestamp = dateTime.getTime();
                previousCoordinates = coordinates;
            }
            line = L.polyline(line, {
                style: {
                    weight: 3,
                    color: '#87f'
                },
                interactive: false
            });
            line.addTo(layerGroup);
            bounds = line.getBounds();
            map.fitBounds(bounds);
            map.setMaxBounds(bounds.pad(.5));
            line.bringToBack();
        });
    }

    window.addEventListener('load', maybeOpenMap);

})();
