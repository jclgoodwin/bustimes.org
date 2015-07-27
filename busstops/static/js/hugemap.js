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
            maxZoom: 17,
            maxBounds: L.latLngBounds([49.004430, -9.408655], [59.76591, 2.5])
        }),
        attribution = 'Map data &copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors | Map tiles &copy; <a href="https://cartodb.com/attributions#basemaps">CartoDB</a>',
        tileURL = (document.location.protocol === 'https:' ? 'https://cartodb-basemaps-{s}.global.ssl.fastly.net' : 'http://{s}.basemaps.cartocdn.com') + '/light_all/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png',
        pin = L.icon({
            iconUrl:    '/static/pin.svg',
            iconSize:   [16, 22],
            iconAnchor: [8, 22],
            popupAnchor: [0, -22],
        }),
        statusBar = L.control({
            position: 'topright'
        }),
        markers = new L.MarkerClusterGroup({
            disableClusteringAtZoom: 14
        });

    statusBar.onAdd = function () {
        var div = L.DomUtil.create('div', 'hugemap-status');
        return div;
    };
    statusBar.addTo(map);

    map.addLayer(markers);

    L.tileLayer(tileURL, {
        attribution: attribution
    }).addTo(map);

    function loadStops(map, statusBar) {
        var bounds = map.getBounds(),
            hw = map.highwater;
        if (!hw || !hw.contains(bounds)) {
            statusBar.getContainer().innerHTML = 'Loading...';
            $.get('/stops.json', {
                ymax: bounds.getNorth(),
                xmax: bounds.getEast(),
                ymin: bounds.getSouth(),
                xmin: bounds.getWest(),
            }, function (data) {
                var layer = L.geoJson(data, {
                    pointToLayer: function (data, latlng) {
                        return L.marker(latlng, {
                            icon: pin
                        }).bindPopup('<a href="' + data.properties.url + '">' + data.properties.name + '</a>');
                    }
                });
                markers.clearLayers();
                layer.addTo(markers);
                map.highwater = bounds;
                statusBar.getContainer().innerHTML = '';
            }, 'json');
        }
    }

    map.on('moveend', function (e) {
        window.location.hash = e.target.getCenter().lat + ',' + e.target.getCenter().lng;
        if (e.target.getZoom() > 10) {
            loadStops(this, statusBar);
        } else {
            statusBar.getContainer().innerHTML = 'Please zoom in to see stops';
        }
    });

    if (window.location.hash) {
        map.setView(window.location.hash.substr(1).split(','), 12);
    } else {
        map.setView([53.833333, -2.416667], 5);
        map.locate({setView: true, maxZoom: 12});
    }

})();
