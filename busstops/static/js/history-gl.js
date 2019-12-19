(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        mapboxgl, reqwest
    */

    mapboxgl.accessToken = 'pk.eyJ1Ijoiamdvb2R3aW4iLCJhIjoiY2pzN3J0bzU5MGp6bzQ5b2txZ3R5anlvOSJ9.X0lgWVi-7yqAEivmYDiDPA';

    var map;

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
                bounds = locations.reduce(function(bounds, location) {
                    return bounds.extend(location.coordinates);
                }, new mapboxgl.LngLatBounds());

            map = new mapboxgl.Map({
                container: mapContainer,
                style: 'mapbox://styles/mapbox/streets-v11',
                bounds: bounds,
                fitBoundsOptions: {
                    padding: 50
                }
            });

            var line = {
                type: 'Feature',
                geometry: {
                    type: 'LineString',
                    coordinates: locations.map(function(location) {
                        return location.coordinates;
                    })
                }
            };

            var minuteMarks = {
                type: 'FeatureCollection',
                features: []
            };

            var previousCoordinates,
                previousTimestamp;

            locations.forEach(function(location) {
                var dateTime = new Date(location.datetime),
                    coordinates = new mapboxgl.LngLat(location.coordinates[0], location.coordinates[1]),
                    delta = location.delta,
                    popup = dateTime.toTimeString().slice(0, 8);

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
                }

                popup = new mapboxgl.Popup({
                    closeButton: false,
                    offset: [2, -4]
                }).setHTML(popup);

                var marker = document.createElement('div');
                marker.className = 'just-arrow';

                new mapboxgl.Marker({
                    element: marker,
                    rotation: (location.direction || 0) - 135,
                }).setLngLat(coordinates).setPopup(popup).addTo(map);

                if (previousCoordinates) {
                    var latDistance = coordinates.lat - previousCoordinates.lat,
                        lngDistance = coordinates.lng - previousCoordinates.lng,
                        minutes = Math.floor(previousTimestamp / 60000) * 60000,
                        timeDistance = dateTime.getTime() - previousTimestamp,
                        latSpeed = latDistance / timeDistance,
                        lngSpeed = lngDistance / timeDistance,
                        j;

                    for (j = previousTimestamp - minutes; j <= timeDistance; j += 60000) {
                        minuteMarks.features.push({
                            type: 'Feature',
                            geometry: {
                                type: 'Point',
                                coordinates: [
                                    previousCoordinates.lng + lngSpeed * j,
                                    previousCoordinates.lat + latSpeed * j
                                ]
                            }
                        });
                    }
                }
                previousTimestamp = dateTime.getTime();
                previousCoordinates = coordinates;
            });

            map.on('load', function() {
                map.addLayer({
                    id: 'line',
                    type: 'line',
                    source: {
                        type: 'geojson',
                        data: line,
                    },
                    layout: {
                        'line-cap': 'round',
                        'line-join': 'round'
                    },
                    paint: {
                        'line-color': '#87f',
                        'line-width': 3,
                    }
                });
                map.addLayer({
                    id: 'minutes',
                    type: 'circle',
                    source: {
                        type: 'geojson',
                        data: minuteMarks,
                    },
                    paint: {
                        'circle-radius': 3
                    }
                });
            });
        });
    }

    maybeOpenMap();
})();
