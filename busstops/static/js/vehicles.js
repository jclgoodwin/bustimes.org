(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest, Cowboy
    */

    var map = L.map('hugemap', {
            minZoom: 6,
            maxZoom: 18,
        }),
        tileURL = 'https://maps.tilehosting.com/styles/basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png?key=RXrAQ6RZ239ClCzC8uZj',
        statusBar = L.control({
            position: 'topright'
        }),
        lastReq,
        timeout,
        oldVehicles = {},
        newVehicles = {};

    L.tileLayer(tileURL, {
        attribution: '© <a href="https://openmaptiles.org">OpenMapTiles</a> | © <a href="https://www.openstreetmap.org">OpenStreetMap contributors</a>'
    }).addTo(map);

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
        if (service) {
            html += service.line_name;
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
        if (data.properties.operator) {
            popup += data.properties.operator + ' ';
        }
        if (data.properties.service) {
            popup += '<a href="' + data.properties.service.url + '/vehicles">' + data.properties.service.line_name + '</a>';
        }
        if (popup) {
            popup += '<br>';
        }

        var dateTime = new Date(data.properties.datetime);
        if (data.properties.vehicle) {
            popup += '<a href="' + data.properties.vehicle.url + '">' + data.properties.vehicle.name + '</a>';
            if (data.properties.vehicle.type) {
                popup += '<br>' + data.properties.vehicle.type;
            }
        }

        if (data.properties.delta === 0) {
            popup += '<br>On time';
        } else if (data.properties.delta) {
            popup += '<br>About ';
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
        popup += '<br>Updated at ' + dateTime.toTimeString().slice(0, 5);

        marker.bindPopup(popup);

        newVehicles[data.properties.vehicle.url] = marker;
    }


    function processData(data) {
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
        statusBar.getContainer().innerHTML = '';
    }

    function load(map, statusBar) {
        statusBar.getContainer().innerHTML = 'Loading\u2026';
        if (lastReq) {
            lastReq.abort();
        }
        var bounds = map.getBounds();
        lastReq = reqwest(
            '/vehicles.json?ymax=' + bounds.getNorth() + '&xmax=' + bounds.getEast() + '&ymin=' + bounds.getSouth() + '&xmin=' + bounds.getWest(),
            function(data) {
                if (data) {
                    processData(data);
                }
                timeout = setTimeout(function() {
                    load(map, statusBar);
                }, 10000);
            }
        );
    }

    function handleMoveEnd(event) {
        var latLng = event.target.getCenter(),
            string = map.getZoom() + '/' + latLng.lat + '/' + latLng.lng;

        localStorage.setItem('vehicleMap', string);

        clearTimeout(timeout);
        load(map, statusBar);
    }

    map.on('moveend', Cowboy.debounce(500, handleMoveEnd));

    if (localStorage.vehicleMap) {
        var parts = localStorage.vehicleMap.split('/');
        map.setView([parts[1], parts[2]], parts[0]);
    } else {
        map.setView([51.9, 0.9], 9);
    }

    load(map, statusBar);
})();
