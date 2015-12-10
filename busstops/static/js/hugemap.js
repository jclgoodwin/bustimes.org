(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, $
    */

    var map = L.map('hugemap', {
            minZoom: 5,
            maxZoom: 13,
            maxBounds: [[60.85, -9.23], [49.84, 2.69]]

        }),
        attribution = 'Map data &copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors | Map tiles &copy; <a href="https://cartodb.com/attributions#basemaps">CartoDB</a>',
        tileURL = (document.location.protocol === 'https:' ? 'https://cartodb-basemaps-{s}.global.ssl.fastly.net' : 'http://{s}.basemaps.cartocdn.com') + '/light_all/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png',
        pin = L.icon({
            iconUrl: '/static/pin.svg',
            iconSize: [16, 22],
            iconAnchor: [8, 22],
            popupAnchor: [0, -22],
        }),
        statusBar = L.control({
            position: 'topright'
        }),
        markers = new L.MarkerClusterGroup();

    statusBar.onAdd = function () {
        var div = L.DomUtil.create('div', 'hugemap-status');
        return div;
    };
    statusBar.addTo(map);

    map.addLayer(markers);

    L.tileLayer(tileURL, {
        attribution: attribution
    }).addTo(map);

    function processStopsData(data) {
        var layer = L.geoJson(data, {
            pointToLayer: function (data, latlng) {
                return L.marker(latlng, {
                    icon: pin
                }).bindPopup('<a href="' + data.properties.url + '">' + data.properties.name + '</a>');
            }
        });
        markers.clearLayers();
        layer.addTo(markers);
        statusBar.getContainer().innerHTML = '';
    }

    function loadStops(map, statusBar) {
        var bounds = map.getBounds(),
            highWater = map.highWater;
        if (!highWater || !highWater.contains(bounds)) {
            statusBar.getContainer().innerHTML = 'Loading\u2026';
            $.get('/stops.json', {
                ymax: bounds.getNorth(),
                xmax: bounds.getEast(),
                ymin: bounds.getSouth(),
                xmin: bounds.getWest(),
            }, processStopsData, 'json');
            map.highWater = bounds;
        }
    }

    map.on('moveend', function (e) {
        window.location.hash = e.target.getZoom() + ',' + e.target.getCenter().lat + ',' + e.target.getCenter().lng;
        if (e.target.getZoom() > 11) {
            loadStops(this, statusBar);
        } else {
            statusBar.getContainer().innerHTML = 'Please zoom in to see stops';
        }
    });

    var parts = window.location.hash.substr(1).split(',');

    if (parts.length === 3) {
        map.setView([parts[1], parts[2]], parts[0]);
    } else {
        statusBar.getContainer().innerHTML = 'Finding your location\u2026';
        map.locate({setView: true});
    }

})();
