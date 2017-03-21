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
        }),
        lastReq,
        movedByAccident;

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
                    movedByAccident = true;
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
        if (lastReq) {
            lastReq.abort();
        }
        lastReq = reqwest(
            '/stops.json?ymax=' + bounds.getNorth() + '&xmax=' + bounds.getEast() + '&ymin=' + bounds.getSouth() + '&xmin=' + bounds.getWest(),
            processStopsData
        );
        map.highWater = bounds;
    }

    function rememberLocation(latLngString) {
        if (history.replaceState) {
            history.replaceState(null, null, window.location.pathname + '#' + latLngString);
        }
        if (localStorage) {
            try {
                localStorage.setItem('location', latLngString);
            } catch (ignore) {
                // never mind
            }
        }
    }

    function handleMoveEnd(event) {
        if (movedByAccident) {
            movedByAccident = false;
            return;
        }

        var latLng = event.target.getCenter(),
            latLngString = Math.round(latLng.lat * 10000) / 10000 + ',' + Math.round(latLng.lng * 10000) / 10000;

        rememberLocation(latLngString);

        if (event.target.getZoom() > 13) {
            loadStops(this, statusBar);
        } else {
            statusBar.getContainer().innerHTML = 'Please zoom in to see stops';
        }
    }

    map.on('moveend', Cowboy.debounce(500, handleMoveEnd));

    map.on('locationfound', function () {
        statusBar.getContainer().innerHTML = '';
    });

    var parts,
        shouldLocate = true;
    if (window.location.hash) {
        parts = window.location.hash.substr(1).split(',');
        shouldLocate = false;
    } else if (localStorage && localStorage.getItem('location')) {
        parts = localStorage.getItem('location').split(',');
    }
    if (parts) {
        map.setView([parts[0], parts[1]], 14);
    } else {
        map.setView([54, -2.5], 6);
    }
    if (shouldLocate) {
        statusBar.getContainer().innerHTML = 'Finding your location\u2026';
        map.locate({setView: true});
    }
})();
