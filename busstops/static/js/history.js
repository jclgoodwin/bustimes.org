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

    var date = document.getElementById('date').value;

    function closeMap() {
        if (lastRequest) {
            lastRequest.abort();
        }
        window.location.hash = ''; // triggers hashchange event
    }

    window.onkeydown = function(event) {
        if (event.keyCode === 27) { // esc
            closeMap();
        }
    };

    var lastRequest;

    window.onhashchange = maybeOpenMap;

    function maybeOpenMap() {
        var journey = window.location.hash.slice(1);

        if (journey) {
            var element = document.getElementById(journey);
        }

        if (!element) {
            return;
        }

        if (lastRequest) {
            lastRequest.abort();
        }

        if (map) {
            map.remove();
            map = null;
        }

        if (element.dataset.trip && !element.querySelector('.trip')) {
            var tripElement = document.createElement('div');
            tripElement.className = 'trip';
            element.appendChild(tripElement);

            reqwest('/trips/' + element.dataset.trip + '.json', function(trip) {
                var table = document.createElement('table');
                var thead = document.createElement('thead');
                thead.innerHTML = '<tr><th>Stop</th><th>Timetable</th></tr>';
                table.appendChild(thead);

                var tbody = document.createElement('tbody');
                var tr, stop, time;
                for (var i = 0; i < trip.stops.length; i++) {
                    tr = document.createElement('tr');
                    stop = trip.stops[i];
                    time = stop.aimed_departure_time || stop.aimed_arrival_time || '';
                    tr.innerHTML = '<td>' + stop.name + '</th><td>' + time + '</td>';
                    tbody.appendChild(tr);
                }
                table.appendChild(tbody);
                tripElement.appendChild(table);
            });
        }

        var mapContainer = element.querySelector('.map');
        if (!mapContainer) {
            if (!mapContainer) {
                mapContainer = document.createElement('div');
                mapContainer.className = 'map';
                element.appendChild(mapContainer);
            }
        }

        reqwest('/' + journey + '.json', function(locations) {
            var layerGroup = L.layerGroup();

            map =  L.map(mapContainer);

            layerGroup.addTo(map);

            map.attributionControl.setPrefix('');

            L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', {
                attribution: '<a href="https://stadiamaps.com/">© Stadia Maps</a> <a href="https://openmaptiles.org/">© OpenMapTiles</a> <a href="https://www.openstreetmap.org/about/">© OpenStreetMap contributors</a>',
            }).addTo(map);

            var i,
                j,
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


            for (i = locations.length - 1; i >= 0; i -= 1) {
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
                weight: 4,
                color: '#87f',
                opacity: .5,
                interactive: false
            });
            line.addTo(layerGroup);
            bounds = line.getBounds();
            map.fitBounds(bounds, {
                maxZoom: 14
            });
            map.setMaxBounds(bounds.pad(.5));
            line.bringToBack();
        });
    }

    window.addEventListener('load', maybeOpenMap);

    function handleClick(event) {
        window.history.replaceState(null, null, window.location.pathname + '?date=' + date + event.target.hash);
        maybeOpenMap();
    }

    document.querySelectorAll('a[href^="#journeys/"]').forEach(function(link) {
        link.addEventListener('click', handleClick);
    });

})();
