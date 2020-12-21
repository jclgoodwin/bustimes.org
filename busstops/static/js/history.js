(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest
    */

    var map;

    function arrowMarker(latLng, direction) {
        direction = (direction || 0) - 135;
        return L.marker(latLng, {
            icon: L.divIcon({
                iconSize: [16, 16],
                html: '<div class="arrow" style="-ms-transform: rotate(' + direction + 'deg);-webkit-transform: rotate(' + direction + 'deg);-moz-transform: rotate(' + direction + 'deg);-o-transform: rotate(' + direction + 'deg);transform: rotate(' + direction + 'deg)"></div>',
                className: 'just-arrow',
            })
        });
    }

    var circleMarkerOptions = {
        radius: 2,
        fillColor: '#000',
        fillOpacity: 1,
        weight: 0,
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

    function getTooltip(delta) {
        if (delta) {
            var tooltip = 'About ';
            if (delta > 0) {
                tooltip += delta;
            } else {
                tooltip += delta * -1;
            }
            tooltip += ' minute';
            if (delta !== 1 && delta !== -1) {
                tooltip += 's';
            }
            if (delta > 0) {
                tooltip += ' early';
            } else {
                tooltip += ' late';
            }
            return '<br>' + tooltip;
        } else if (delta === 0) {
            return '<br>On time';
        } else {
            return '';
        }
    }

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

        reqwest('/' + journey + '.json', function(response) {

            if (response.stops) {
                var tripElement = document.createElement('div');
                tripElement.className = 'trip';
                element.appendChild(tripElement);

                var table = document.createElement('table');
                var thead = document.createElement('thead');
                thead.innerHTML = '<tr><th>Stop</th><th>Timetable</th></tr>';
                table.appendChild(thead);

                var tbody = document.createElement('tbody');
                var tr, stop, time;
                for (var i = 0; i < response.stops.length; i++) {
                    tr = document.createElement('tr');
                    stop = response.stops[i];
                    time = stop.aimed_departure_time || stop.aimed_arrival_time || '';
                    tr.innerHTML = '<td>' + stop.name + '</th><td>' + time + '</td>';
                    tbody.appendChild(tr);
                }
                table.appendChild(tbody);
                tripElement.appendChild(table);
            }

            var mapContainer = element.querySelector('.map');
            if (!mapContainer) {
                mapContainer = document.createElement('div');
                mapContainer.className = 'map';
                element.appendChild(mapContainer);
            }

            var locations = response.locations;

            map =  L.map(mapContainer);

            map.attributionControl.setPrefix('');

            L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', {
                attribution: '<a href="https://stadiamaps.com/">© Stadia Maps</a> <a href="https://openmaptiles.org/">© OpenMapTiles</a> <a href="https://www.openstreetmap.org/about/">© OpenStreetMap contributors</a>',
            }).addTo(map);

            var line = [];

            var previousCoordinates,
                previousTimestamp;

            locations.forEach(function(location) {
                var dateTime = new Date(location.datetime);
                var popup = dateTime.toTimeString().slice(0, 8);
                var timestamp = dateTime.getTime();
                popup += getTooltip(location.delta);

                var coordinates = L.latLng(location.coordinates[1], location.coordinates[0]);

                arrowMarker(coordinates, location.direction).bindTooltip(popup).addTo(map);

                line.push(coordinates);

                if (previousCoordinates) {
                    var time = timestamp - previousTimestamp;  

                    if (time) {
                        var latDistance = coordinates.lat - previousCoordinates.lat;
                        var lngDistance = coordinates.lng - previousCoordinates.lng;
                        var latSpeed = latDistance / time;
                        var lngSpeed = lngDistance / time;


                        var minute = Math.ceil(previousTimestamp / 60000) * 60000 - previousTimestamp;
                        for (; minute <= time; minute += 60000) {
                            L.circleMarker(L.latLng(
                                previousCoordinates.lat + latSpeed * minute,
                                previousCoordinates.lng + lngSpeed * minute
                            ), circleMarkerOptions).addTo(map);
                        }
                    }
                }

                previousCoordinates = coordinates;
                previousTimestamp = timestamp;
            });


            line = L.polyline(line, {
                weight: 4,
                color: '#87f',
                opacity: .5
            });
            line.addTo(map);

            var bounds = line.getBounds();

            map.fitBounds(bounds, {
                maxZoom: 14
            }).setMaxBounds(bounds.pad(.5));
        });
    }

    window.addEventListener('load', maybeOpenMap);

    function handleClick(event) {
        window.history.replaceState(null, null, window.location.pathname + '?date=' + date + event.target.hash);
        maybeOpenMap();
    }

    Array.from(document.querySelectorAll('a[href^="#journeys/"]')).forEach(function(link) {
        link.addEventListener('click', handleClick);
    });

})();
