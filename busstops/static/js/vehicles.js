(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest
    */

    var map = L.map('hugemap', {
            minZoom: 6,
            maxZoom: 18,
        }),
        tileURL = 'https://bustimes.org/styles/klokantech-basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png',
        statusBar = L.control({
            position: 'topright'
        }),
        layer,
        lastReq;

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

    function processData(data) {
        layer && layer.clearLayers();
        layer = L.geoJson(data, {
            pointToLayer: function (data, latlng) {
                var marker = L.marker(latlng, {
                    icon: getIcon(data.properties.service, data.properties.direction)
                });

                var popup = '';
                if (data.properties.operator) {
                    popup += data.properties.operator + '<br>';
                }
                if (data.properties.service) {
                    popup += '<a href="' + data.properties.service.url + '">' + data.properties.service.line_name + ' - ' + data.properties.service.description + '</a><br>';
                }

                var dateTime = new Date(data.properties.datetime);
                if (data.properties.vehicle) {
                    popup += '<a href="' + data.properties.vehicle.url + '">' + data.properties.vehicle.name + '</a>';
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

                return marker;
            }
        });
        layer.addTo(map);
        statusBar.getContainer().innerHTML = '';
    }

    function load(map, statusBar) {
        statusBar.getContainer().innerHTML = 'Loading\u2026';
        if (lastReq) {
            lastReq.abort();
        }
        lastReq = reqwest('/vehicles.json', function(data) {
            processData(data);
            setTimeout(function() {
                load(map, statusBar);
            }, 10000);
        });
    }

    map.setView([52.6, 1.1], 10);

    load(map, statusBar);
})();
