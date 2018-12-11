(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest
    */

    var map = L.map('map', {
            tap: false
        }),
        tileURL = 'https://bustimes.org/styles/klokantech-basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png',
        polyline,
        busesOnlineCount = document.getElementById('buses-online-count'),
        statusBar = L.control({
            position: 'topright'
        }),
        bounds,
        lastReq,
        oldVehicles = {},
        newVehicles = {};

    L.tileLayer(tileURL, {
        attribution: '© <a href="https://openmaptiles.org">OpenMapTiles</a> | © <a href="https://www.openstreetmap.org">OpenStreetMap contributors</a>'
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

    function getIcon(service, direction) {
        if (direction !== null) {
            var html = '<div class="arrow" style="-ms-transform: rotate(' + direction + 'deg);-webkit-transform: rotate(' + direction + 'deg);-moz-transform: rotate(' + direction + 'deg);-o-transform: rotate(' + direction + 'deg);transform: rotate(' + direction + 'deg)"></div>';
        } else {
            html = '';
        }
        return L.divIcon({
            iconSize: [20, 20],
            html: html,
            popupAnchor: [0, -5],
            className: 'leaflet-div-icon'
        });
    }

    function handleVehicle(data) {
        var marker,
            icon = getIcon(data.properties.service, data.properties.direction),
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

        if (data.properties.vehicle && data.properties.vehicle.type) {
            popup = data.properties.vehicle.type + '<br>' + popup;
        }

        var dateTime = new Date(data.properties.datetime);
        popup += 'Updated at ' + dateTime.toTimeString().slice(0, 5);

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
                padding: [20, 20],
                maxZoom: 12
            });
        }
        statusBar.getContainer().innerHTML = '';
    }

    function load(map, statusBar) {
        statusBar.getContainer().innerHTML = 'Loading\u2026';
        if (lastReq) {
            lastReq.abort();
        }
        lastReq = reqwest('/vehicles.json?service=' + map.getContainer().getAttribute('data-service'), function(data) {
            if (lastReq.request.status === 200 && data && data.features) {
                processData(data);
            }
            setTimeout(function() {
                load(map, statusBar);
            }, 10000);
        });
    }

    if (busesOnlineCount) {
        load(map, statusBar);
    }
})();
