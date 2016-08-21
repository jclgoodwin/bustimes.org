(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, $
    */

    var map = L.map('hugemap', {
            minZoom: 6,
            maxBounds: [[60.85, -9.23], [49.84, 2.69]]
        }),
        tileURL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        attribution = '© <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
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
            disableClusteringAtZoom: 15,
            maxClusterRadius: 50
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

    function processStopsData(data) {
        var sidebar = document.getElementById('sidebar');
        sidebar.innerHTML = '<h2>Stops</h2>';
        var ul = document.createElement('ul');
        var layer = L.geoJson(data, {
            pointToLayer: function (data, latlng) {
                var li = document.createElement('li');
                var a = document.createElement('a');
                var marker = L.marker(latlng, {
                    icon: pin
                });

                a.innerHTML = data.properties.name;
                a.href = data.properties.url;

                marker.bindPopup(a.outerHTML);

                a.onmouseover = function() {
                    window.movedByAccident = true;
                    marker.openPopup();
                };

                li.appendChild(a);
                ul.appendChild(li);

                return marker;
            }
        });
        sidebar.appendChild(ul);
        markers.clearLayers();
        layer.addTo(markers);
        statusBar.getContainer().innerHTML = '';

    }

    function loadStops(map, statusBar) {
        var bounds = map.getBounds();
        statusBar.getContainer().innerHTML = 'Loading\u2026';
        reqwest(
            '/stops.json?ymax=' + bounds.getNorth() + '&xmax=' + bounds.getEast() + '&ymin=' + bounds.getSouth() + '&xmin=' + bounds.getWest(),
            processStopsData
        );
        map.highWater = bounds;
    }

    map.on('moveend', function (e) {
        if (window.movedByAccident) {
            window.movedByAccident = false;
            return;
        }

        var latLng = e.target.getCenter();
        var latLngString = Math.round(latLng.lat * 10000) / 10000 + ',' + Math.round(latLng.lng * 10000) / 10000;

        history.replaceState(null, null, window.location.pathname + '#' + latLngString);
        localStorage.setItem('location', latLngString);

        if (e.target.getZoom() > 13) {
            loadStops(this, statusBar);
        } else {
            statusBar.getContainer().innerHTML = 'Please zoom in to see stops';
        }
    });

    map.on('locationfound', function (event) {
        localStorage.setItem('location', event.latitude.toString() + ',' + event.longitude);
    });

    var parts;
    if (window.location.hash) {
        parts = window.location.hash.substr(1).split(',');
    } else if (localStorage && localStorage.getItem('location')) {
        parts = localStorage.getItem('location').split(',');
    }
    if (parts) {
        map.setView([parts[0], parts[1]], 14);
    } else {
        statusBar.getContainer().innerHTML = 'Finding your location\u2026';
        map.locate({setView: true});
    }

})();
