(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest
    */

    var map = L.map('map'),
        tileURL = 'https://maps.bustimes.org/styles/klokantech-basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png',
        polyline,
        statusBar = L.control({
            position: 'bottomleft'
        }),
        bounds,
        lastReq,
        oldVehicles = {},
        newVehicles = {},
        first = true,
        busesOnline = document.getElementById('buses-online'),
        button = busesOnline.getElementsByTagName('button')[0];

    map.attributionControl.setPrefix('');

    L.tileLayer(tileURL, {
        attribution: '<a href="https://www.maptiler.com/copyright/">© MapTiler</a> <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>'
    }).addTo(map);

    button.onclick = function() {
        map.getContainer().className += ' expanded';
        document.body.style.overflow = 'hidden';

        map.invalidateSize();

        if (first && window.geometry) {
            polyline = L.geoJson(window.geometry, {
                style: {
                    weight: 2
                }
            });
            polyline.addTo(map);
            bounds = polyline.getBounds();
            map.fitBounds(bounds);
            map.setMaxBounds(bounds.pad(1));
            first = false;
        }
    };

    statusBar.onAdd = function () {
        var div = L.DomUtil.create('div', 'hugemap-status');
        return div;
    };
    statusBar.addTo(map);

    function getRotation(direction) {
        if (direction == null) {
            return '';
        }
        var rotation = 'transform: rotate(' + direction + 'deg)';
        return '-ms-' + rotation + ';-webkit-' + rotation + ';-moz-' + rotation + ';-o-' + rotation + ';' + rotation;
    }

    function getIcon(direction, livery, textColour) {
        if (direction == null) {
            var html = '';
        } else {
            html = '<div class="arrow" style="' + getRotation(direction) + '"></div>';
            if (direction < 180) {
                direction -= 90;
            } else {
                direction -= 270;
            }
        }
        var className = 'bus';
        if (livery) {
            var style = 'background:' + livery + ';';
            className += ' coloured';
            if (textColour) {
                className += ' white-text';
            }
        } else {
            style = '';
        }
        style += getRotation(direction);
        html += '<div class="' + className + '" style="' + style + '"></div>';
        return L.divIcon({
            iconSize: [20, 20],
            html: html,
            popupAnchor: [0, -5],
        });
    }

    function handleVehicle(data) {
        var props = data.properties;

        if (props.vehicle.url in oldVehicles) {
            var marker = oldVehicles[props.vehicle.url];
            newVehicles[props.vehicle.url] = marker;
            if (marker.datetime === props.datetime) {
                return;
            }
        }

        var icon = getIcon(props.direction, props.vehicle.livery, props.vehicle.text_colour),
            latLng = L.latLng(data.geometry.coordinates[1], data.geometry.coordinates[0]);

        bounds.extend(latLng);

        if (marker) {
            marker.setLatLng(latLng);
            marker.setIcon(icon);
        } else {
            marker = L.marker(latLng, {
                icon: icon
            });
            marker.addTo(map);
            newVehicles[props.vehicle.url] = marker;
        }
        marker.datetime = props.datetime;

        var popup = '';

        if (props.delta === 0) {
            popup += 'On time';
        } else if (props.delta) {
            popup += 'About ';
            if (props.delta > 0) {
                popup += props.delta;
            } else {
                popup += props.delta * -1;
            }
            popup += ' minute';
            if (props.delta !== 1 && props.delta !== -1) {
                popup += 's';
            }
            if (props.delta > 0) {
                popup += ' early';
            } else {
                popup += ' late';
            }
        }

        if (popup) {
            popup += '<br>';
        }

        if (props.destination) {
            popup = props.destination + '<br>' + popup;
            if (props.destination.indexOf(' to ') === -1) {
                popup = 'To ' + popup;
            }
        }

        var dateTime = new Date(props.datetime);
        popup += 'Updated at ' + dateTime.toTimeString().slice(0, 5);

        if (props.vehicle.decker) {
            var vehicleFeatures = 'Double-decker';
            if (props.vehicle.coach) {
                vehicleFeatures += ' coach';
            }
            popup = vehicleFeatures + '<br>' + popup;
        } else if (props.vehicle.coach) {
            popup = 'Coach' + '<br>' + popup;
        }

        popup = props.vehicle.name + '<br>' + popup;

        marker.bindPopup(popup);
    }

    function processData(data) {
        bounds = L.latLngBounds();

        for (var i = data.features.length - 1; i >= 0; i -= 1) {
            handleVehicle(data.features[i]);
        }
        for (var vehicle in oldVehicles) {
            if (!(vehicle in newVehicles)) {
                map.removeLayer(oldVehicles[vehicle]);
            }
        }
        oldVehicles = newVehicles;
        newVehicles = {};

        if (!map._loaded && bounds.isValid()) {
            map.fitBounds(bounds, {
                padding: [10, 10],
                maxZoom: 12
            });
        }
        statusBar.getContainer().innerHTML = '';
    }

    var timeout, busesOnlineCount;

    function load(map, statusBar) {
        statusBar.getContainer().innerHTML = 'Loading\u2026';
        if (lastReq) {
            lastReq.abort();
        }
        lastReq = reqwest('/vehicles.json?service=' + map.getContainer().getAttribute('data-service'), function(data) {
            if (lastReq.request.status === 200 && data && data.features) {
                if (!busesOnlineCount) { // first load
                    if (data.features.length) {
                        busesOnlineCount = document.createElement('span');
                        busesOnline.appendChild(busesOnlineCount);
                        if (document.addEventListener) {
                            document.addEventListener('visibilitychange', handleVisibilityChange);
                        }
                    } else {
                        statusBar.getContainer().innerHTML = '';
                        return;
                    }
                }

                if (data.features.length === 0) {
                    busesOnlineCount.innerHTML = 'No buses online';
                } else if (data.features.length === 1) {
                    busesOnlineCount.innerHTML = '1 bus online';
                } else {
                    busesOnlineCount.innerHTML = data.features.length + ' buses online';
                }
                processData(data);
            }
            timeout = setTimeout(function() {
                load(map, statusBar);
            }, 10000);
        });
    }

    function handleVisibilityChange(event) {
        if (event.target.hidden) {
            clearTimeout(timeout);
        } else {
            load(map, statusBar);
        }
    }

    function closeMap() {
        var container = map.getContainer();
        container.className = container.className.replace(' expanded', '');
        document.body.style.overflow = '';

        return false;
    }

    window.onkeydown = function(event) {
        if (event.keyCode === 27) {
            closeMap();
        }
    };

    var closeButton = L.control();

    closeButton.onAdd = function(map) {
        var div = document.createElement('div');
        div.className = 'leaflet-bar';

        var a = document.createElement('a');
        a.href = '#';
        a.style.width = 'auto';
        a.style.padding = '0 8px';
        a.setAttribute('role', 'button');
        a.innerHTML = 'Close map';
        a.onclick = closeMap;

        div.appendChild(a);
        return div;
    };

    closeButton.addTo(map);

    load(map, statusBar);
})();
