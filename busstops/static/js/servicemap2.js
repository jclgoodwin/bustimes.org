(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest, loadjs, bustimes
    */

    var container = document.getElementById('map'),
        service = container.getAttribute('data-service'),
        map,
        busesOnline = document.getElementById('buses-online'),
        button = busesOnline.getElementsByTagName('a')[0];

    function setLocationHash(hash) {
        if (history.replaceState) {
            try {
                history.replaceState(null, null, hash || '#');
            } catch (error) {
                // probably SecurityError (document is not fully active)
            }
        }
    }

    function openMap() {
        container.className += ' expanded';
        if (document.body.style.paddingTop) {
            container.style.top = document.body.style.paddingTop;
        }

        setLocationHash('#map');

        if (map) {
            document.body.style.overflow = 'hidden';
            map.invalidateSize();
        } else {
            loadjs([window.LEAFLET_CSS_URL, window.MAPS_JS_URL, window.LEAFLET_JS_URL], setUpMap);
            if (window.SERVICE_TRACKING) {
                loadjs(window.LIVERIES_CSS_URL);
            }
        }
    }

    button.onclick = openMap;

    function getStopMarker(feature, latlng) {
        if (feature.properties.bearing !== null) {
            var html = '<div class="stop-arrow" style="' + bustimes.getTransform(feature.properties.bearing + 45) + '"></div>';
        } else {
            html = '<div class="stop-arrow no-direction"></div>';
        }
        var icon = L.divIcon({
            iconSize: [9, 9],
            html: html,
            className: 'stop'
        });

        return L.marker(latlng, {
            icon: icon
        }).bindPopup('<a href="' + feature.properties.url + '">' + feature.properties.name + '</a>');
    }

    function setUpMap() {
        if (map) {
            return;
        }

        document.body.style.overflow = 'hidden';

        map = L.map(container);

        bustimes.map = map;

        bustimes.doTileLayer(map);

        loadjs(window.LOCATE_JS_URL, function() {
            L.control.locate().addTo(map);
        });

        var closeButton = L.control();

        closeButton.onAdd = function() {
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

        if (window.EXTENT) {
            map.fitBounds([[window.EXTENT[1], window.EXTENT[0]], [window.EXTENT[3], window.EXTENT[2]]]);
        }

        reqwest('/services/' + service.split(',')[0] + '.json', function(data) {
            L.geoJson(data.geometry, {
                style: {
                    weight: 3,
                    color: '#87f'
                },
                interactive: false
            }).addTo(map);

            L.geoJson(data.stops, {
                pointToLayer: getStopMarker
            }).addTo(map);
        });

        loadVehicles();
    }

    var vehiclesCount = 0;

    function handleVehicles(items) {
        if (items.length !== vehiclesCount) {
            vehiclesCount = items.length;

            if (!busesOnlineCount) { // first load
                busesOnlineCount = document.createElement('span');
                busesOnline.appendChild(busesOnlineCount);
            }
            if (vehiclesCount === 1) {
                busesOnlineCount.innerHTML = 'Tracking 1 bus';
            } else {
                busesOnlineCount.innerHTML = 'Tracking ' + vehiclesCount + ' buses';
            }
        }

        if (map) {
            bustimes.handleVehicles(items);
        }
    }

    var busesOnlineCount, loadVehiclesTimeout;

    function loadVehicles() {
        if (!window.SERVICE_TRACKING) {
            return;
        }

        var params = '?service=' + service;
        reqwest(
            '/vehicles.json' + params,
            function(data) {
                if (data) {
                    handleVehicles(data);
                }
                if (map && data.length) {
                    loadVehiclesTimeout = setTimeout(loadVehicles, 10000);
                }
            }
        );
    }

    function closeMap() {
        container.className = container.className.replace(' expanded', '');
        document.body.style.overflow = '';
        setLocationHash('');

        if (loadVehiclesTimeout) {
            clearTimeout(loadVehiclesTimeout);
        }

        return false;
    }

    window.onkeydown = function(event) {
        if (event.keyCode === 27) {
            closeMap();
        }
    };

    window.onhashchange = function(event) {
        if (event.target.location.hash === '#map') {
            openMap();
        } else {
            closeMap();
        }
    };

    function handleVisibilityChange(event) {
        if (event.target.hidden) {
            if (loadVehiclesTimeout) {
                clearTimeout(loadVehiclesTimeout);
            }
        } else {
            loadVehicles();
        }
    }

    if (document.addEventListener) {
        document.addEventListener('visibilitychange', handleVisibilityChange);
    }

    if (window.location.hash === '#map') {
        openMap();
    } else {
        loadVehicles();
    }

})();
