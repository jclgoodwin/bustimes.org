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

    var loadVehiclesTimeout,
        poppedUp = false;

    function loadVehicles() {
        if (window.SERVICE) {
            var params = '?service=' + window.SERVICE + '&trip=' +  window.TRIP_ID;
        } else if (window.VEHICLE_ID) {
            params = '?id=' + window.VEHICLE_ID;
        } else {
            return;
        }
        reqwest(
            '/vehicles.json' + params,
            function(data) {
                if (data) {
                    window.bustimes.handleVehicles(data);

                    if (!window.bustimes.clickedMarker && (window.TRIP_ID || window.VEHICLE_ID) && !poppedUp) {
                        for (var id in window.bustimes.vehicleMarkers) {
                            var marker = window.bustimes.vehicleMarkers[id];
                            if (marker.options.item.trip_id === window.TRIP_ID || marker.options.item.id === window.VEHICLE_ID) {
                                marker.openPopup();
                                poppedUp = id;  // don't auto-open the popup again
                                break;
                            }
                        }
                    }

                    if (poppedUp) {
                        var progress = window.bustimes.vehicleMarkers[poppedUp].options.item.progress;
                        if (progress) {
                            // highlight last visited stop in timetable
                            var nowAtStop = window.bustimes.vehicleMarkers[poppedUp].options.item.progress.prev_stop;
                            var wasAtStop = document.querySelector('.referrer');
                            if (wasAtStop) {
                                wasAtStop.classList.remove('referrer');
                            }
                            nowAtStop = document.querySelector('[href="/stops/' + nowAtStop + '"]').parentNode.parentNode;
                            nowAtStop.classList.add('referrer');
                        }
                    }
                }

                if (data.length) {
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
        var map = L.map('map', {
            tap: false
        });

        window.bustimes.doTileLayer(map);

        window.bustimes.map = map;

        var bounds = L.latLngBounds(),
            previousLocation;

        window.STOPS.times.forEach(function(time) {
            var stop = time.stop;
            if (!stop.location) {
                return;
            }

            var location = L.GeoJSON.coordsToLatLng(stop.location);

            if (time.track) {
                L.geoJSON({
                    type: 'LineString',
                    coordinates: time.track,
                }, {
                    interactive: false,
                }).addTo(map);
            } else if (previousLocation) {
                L.polyline(
                    [previousLocation, location],
                    {
                        dashArray: '4',
                        interactive: false,
                    }
                ).addTo(map);
            }

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
            }).bindTooltip(time.aimed_arrival_time || time.aimed_departure_time).addTo(map);

            bounds.extend(location);

            previousLocation = location;
        });

        map.fitBounds(bounds);

        loadVehicles();

        if (document.addEventListener) {
            document.addEventListener('visibilitychange', handleVisibilityChange);
        }

        L.control.locate().addTo(map);
    }
})();
