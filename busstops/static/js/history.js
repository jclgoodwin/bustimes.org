(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest
    */

    var map;

    function arrowMarker(location) {
        var direction = (location.direction || 0) - 135;
        var tooltip = location.datetime.toTimeString().slice(0, 8);
        tooltip += getTooltip(location.delta);

        return L.marker(location.coordinates, {
            icon: L.divIcon({
                iconSize: [16, 16],
                html: '<div class="arrow" style="-webkit-transform: rotate(' + direction + 'deg);transform: rotate(' + direction + 'deg)"></div>',
                className: 'just-arrow',
            })
        }).bindTooltip(tooltip);

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

    var stops, locations, rovingTooltipMarker;

    function showStopOnMap() {
        var stop = stops[this.rowIndex - 1];

        map.eachLayer(function(layer) {
            if (layer.options.pane === 'tooltipPane') layer.removeFrom(map);
        });

        if (!stop.coordinates) {
            return;
        }

        var min = 1000, nearest, location, distance;

        for (var i = 0; i < locations.length; i++) {
            location = locations[i];
            distance = stop.coordinates.distanceTo(location.coordinates);
            if (distance < min) {
                min = distance;
                nearest = location;
            }
        }

        if (nearest) {
            var popup = nearest.datetime.toTimeString().slice(0, 8);
            popup += getTooltip(nearest.delta);

            if (!rovingTooltipMarker) {
                rovingTooltipMarker = L.circleMarker(nearest.coordinates, circleMarkerOptions).addTo(map);
            } else {
                rovingTooltipMarker.setLatLng(nearest.coordinates);
            }
            rovingTooltipMarker.bindTooltip(popup).openTooltip();
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
            var i;

            for (i = 0; i < response.locations.length; i++) {
                var location = response.locations[i];
                location.coordinates = L.latLng(location.coordinates[1], location.coordinates[0]);
                location.datetime = new Date(location.datetime);
            }

            if (response.stops) {
                var tripElement = document.createElement('div');
                tripElement.className = 'trip';
                element.appendChild(tripElement);

                var table = document.createElement('table');
                table.className = 'trip-timetable';
                var thead = document.createElement('thead');
                thead.innerHTML = '<tr><th>Stop</th><th>Timetable</th></tr>';
                table.appendChild(thead);

                var tbody = document.createElement('tbody');
                var tr, stop, time;
                for (i = 0; i < response.stops.length; i++) {
                    tr = document.createElement('tr');
                    stop = response.stops[i];
                    if (stop.minor) {
                        tr.className = 'minor';
                    }
                    time = stop.aimed_departure_time || stop.aimed_arrival_time || '';
                    tr.innerHTML = '<td>' + stop.name + '</th><td>' + time + '</td>';
                    tbody.appendChild(tr);

                    if (stop.coordinates) {
                        stop.coordinates = L.latLng(stop.coordinates[1], stop.coordinates[0]);
                    }
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

            map = L.map(mapContainer);

            window.bustimes.doTileLayer(map);

            L.control.locate().addTo(map);

            var line = [],
                previousCoordinates,
                previousTimestamp,
                previousMarkerCoordinates,
                previousDroppedLocation;

            response.locations.forEach(function(location) {
                var timestamp = location.datetime.getTime();

                var coordinates = location.coordinates;

                line.push(coordinates);

                if (previousCoordinates) {
                    var time = timestamp - previousTimestamp;

                    if (time) {
                        if (previousMarkerCoordinates.distanceTo(location.coordinates) > 100) {
                            if (previousDroppedLocation) {
                                arrowMarker(previousDroppedLocation).addTo(map);
                            }
                            previousDroppedLocation = null;
                            arrowMarker(location).addTo(map);
                            previousMarkerCoordinates = location.coordinates;
                        } else {
                            // not moved far from the last marker
                            previousDroppedLocation = location;
                        }

                        // add a marker every minute
                        if (time < 6000000) {  // less than 10 minutes
                            var latDistance = coordinates.lat - previousCoordinates.lat;
                            var lngDistance = coordinates.lng - previousCoordinates.lng;
                            var latSpeed = latDistance / time;  // really velocity
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
                } else {
                    arrowMarker(location).addTo(map);
                    previousMarkerCoordinates = location.coordinates;
                }

                previousCoordinates = coordinates;
                previousTimestamp = timestamp;
            });
            if (previousDroppedLocation) { 
                arrowMarker(previousDroppedLocation).addTo(map);
            }

            if (response.stops) {
                stops = response.stops;
                locations = response.locations;
                for (i = 0; i < tbody.children.length; i++) {
                    tr = tbody.children[i];
                    tr.addEventListener('mouseover', showStopOnMap);
                    tr.addEventListener('touchstart', showStopOnMap);
                }
            }

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
        window.history.replaceState(null, null, '?date=' + date + event.target.hash);
        maybeOpenMap();
    }

    var links = document.querySelectorAll('a[href^="#journeys/"]');
    for (var i = links.length - 1; i >= 0; i -= 1) {
        links[i].addEventListener('click', handleClick);
    }

})();
