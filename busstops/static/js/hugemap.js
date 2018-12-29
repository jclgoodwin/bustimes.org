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
        tileURL = 'https://bustimes.org/styles/klokantech-basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png',
        statusBar = L.control({
            position: 'topright'
        }),
        markers = new L.MarkerClusterGroup({
            disableClusteringAtZoom: 15,
            maxClusterRadius: 50
        }),
        lastReq;

    L.tileLayer(tileURL, {
        attribution: '© <a href="https://openmaptiles.org">OpenMapTiles</a> | © <a href="https://www.openstreetmap.org">OpenStreetMap contributors</a>'
    }).addTo(map);

    statusBar.onAdd = function () {
        var div = L.DomUtil.create('div', 'hugemap-status');
        return div;
    };
    statusBar.addTo(map);

    markers.on('clustermouseover', function(e) {
        e.layer.spiderfy();
    });
    markers.on('mouseover', function(e) {
        e.layer.openPopup();
    });

    map.addLayer(markers);

    function getRotation(direction) {
        if (direction == null) {
            return '';
        }
        var rotation = 'transform: rotate(' + direction + 'deg)';
        rotation = '-ms-' + rotation + ';-webkit-' + rotation + ';-moz-' + rotation + ';-o-' + rotation + ';' + rotation;
        return ' style="' + rotation + '"';
    }

    function getIcon(indicator, bearing) {
        var className = 'leaflet-div-icon';
        if (indicator) {
            var indicatorParts = indicator.split(' ');
            var firstPart = indicatorParts[0].toLowerCase();
            if (indicatorParts.length === 2 && (firstPart === 'stop' || firstPart === 'bay' || firstPart === 'stand' || firstPart === 'stance')) {
                indicator = indicatorParts[1];
            } else {
                indicator = indicator.slice(0, 3);
            }
        } else {
            indicator = '';
        }
        indicator = '<div class="stop">' + indicator + '</div>';
        if (bearing !== null) {
            indicator += '<div class="arrow"' + getRotation(bearing) + '></div>';
        }
        return L.divIcon({
            iconSize: [20, 20],
            html: indicator,
            popupAnchor: [0, -5],
            className: className
        });
    }

    function processStopsData(data) {
        var sidebar = document.getElementById('sidebar');
        sidebar.innerHTML = '<h2>Stops</h2>';
        var ul = document.createElement('ul');
        var layer = L.geoJson(data, {
            pointToLayer: function (data, latlng) {
                var li = document.createElement('li');
                var a = document.createElement('a');
                var marker = L.marker(latlng, {
                    icon: getIcon(data.properties.indicator, data.properties.bearing)
                });

                a.innerHTML = data.properties.name;
                a.href = data.properties.url;

                marker.bindPopup(a.outerHTML, {
                    autoPan: false
                });

                a.onmouseover = a.ontouchstart = function() {
                    if (!marker.getPopup().isOpen()) {
                        var parent = markers.getVisibleParent(marker);
                        if (parent && parent.spiderfy) {
                            parent.spiderfy();
                        }
                        marker.openPopup();
                    }
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
        try {
            localStorage.setItem('location', latLngString);
        } catch (ignore) {
            // localStorage disabled
        }
    }

    function handleMoveEnd(event) {
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
    } else {
        try {
            if (localStorage.getItem('location')) {
                parts = localStorage.getItem('location').split(',');
            }
        } catch (ignore) {
            // localStorage disabled
        }
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
