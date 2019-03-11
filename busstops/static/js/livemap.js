(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest
    */

    var map = L.map('map', {
            tap: false,
            scrollWheelZoom: false,
        }),
        tileURL = 'https://maps.bustimes.org/styles/klokantech-basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png',
        polyline,
        statusBar = L.control({
            position: 'topright'
        }),
        bounds,
        lastReq,
        oldVehicles = {},
        newVehicles = {};

    map.attributionControl.setPrefix('');

    L.tileLayer(tileURL, {
        attribution: '<a href="https://www.maptiler.com/copyright/">© MapTiler</a> <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>'
    }).addTo(map);

    if (window.geometry) {
        polyline = L.geoJson(window.geometry, {
            style: {
                weight: 2
            }
        });
        polyline.addTo(map);
        map.fitBounds(polyline.getBounds());
    }

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
        if (direction < 180) {
            direction -= 90;
        } else {
            direction -= 270;
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
        var marker,
            icon = getIcon(data.properties.direction, data.properties.vehicle.livery, data.properties.vehicle.text_colour),
            latLng = L.latLng(data.geometry.coordinates[1], data.geometry.coordinates[0]);

        bounds.extend(latLng);

        if (data.properties.vehicle.url in oldVehicles) {
            marker = oldVehicles[data.properties.vehicle.url];
            marker.setLatLng(latLng);
            marker.setIcon(icon);
        } else {
            marker = L.marker(latLng, {
                icon: icon
            });
            marker.addTo(map);
        }

        var popup = '';

        if (data.properties.delta === 0) {
            popup += 'On time';
        } else if (data.properties.delta) {
            popup += 'About ';
            if (data.properties.delta > 0) {
                popup += data.properties.delta;
            } else {
                popup += data.properties.delta * -1;
            }
            popup += ' minute';
            if (data.properties.delta !== 1 && data.properties.delta !== -1) {
                popup += 's';
            }
            if (data.properties.delta > 0) {
                popup += ' early';
            } else {
                popup += ' late';
            }
        }

        if (popup) {
            popup += '<br>';
        }

        if (data.properties.destination) {
            popup = 'To ' + data.properties.destination + '<br>' + popup;
        }

        var dateTime = new Date(data.properties.datetime);
        popup += 'Updated at ' + dateTime.toTimeString().slice(0, 5);

        popup = data.properties.vehicle.name + '<br>' + popup;

        marker.bindPopup(popup);

        newVehicles[data.properties.vehicle.url] = marker;
    }

    function processData(data) {
        if (data.features.length === 0) {
            busesOnlineCount.innerHTML = 'No buses online.';
        } else if (data.features.length === 1) {
            busesOnlineCount.innerHTML = '1 bus online.';
        } else {
            busesOnlineCount.innerHTML = data.features.length + ' buses online.';
        }

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
                        var p = document.getElementById('buses-online');
                        p.innerHTML = '<strong id="buses-online-count"></strong> Click on a bus to see when it last updated';
                        busesOnlineCount = document.getElementById('buses-online-count');
                        document.addEventListener('visibilitychange', handleVisibilityChange);
                    } else {
                        statusBar.getContainer().innerHTML = '';
                        return;
                    }
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

    load(map, statusBar);
})();
