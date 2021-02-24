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
        document.body.style.overflow = 'hidden';

        setLocationHash('#map');

        if (map) {
            map.invalidateSize();
        } else {
            loadjs([window.LEAFLET_CSS_URL, window.MAPS_JS_URL, window.LEAFLET_JS_URL], setUpMap);
            if (window.SERVICE_TRACKING) {
                loadjs('/liveries.css');
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
        map = L.map(container),

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

    function handlePopupOpen(event) {
        var marker = event.target;
        var item = marker.options.item;

        bustimes.clickedMarker = item.id;
        bustimes.updatePopupContent();

        marker.setIcon(bustimes.getBusIcon(item, true));
        marker.setZIndexOffset(2000);
    }

    function handlePopupClose(event) {
        if (map.hasLayer(event.target)) {
            bustimes.clickedMarker = null;
            // make the icon small again
            event.target.setIcon(bustimes.getBusIcon(event.target.options.item));
            event.target.setZIndexOffset(1000);
        }
    }

    function handleVehicle(item) {
        var isClickedMarker = item.id === bustimes.clickedMarker,
            icon = bustimes.getBusIcon(item, isClickedMarker),
            latLng = L.latLng(item.coordinates[1], item.coordinates[0]);

        if (item.id in bustimes.vehicleMarkers) {
            // update existing
            var marker = bustimes.vehicleMarkers[item.id];
            marker.setLatLng(latLng);
            marker.setIcon(icon);
            marker.options.item = item;
            if (isClickedMarker) {
                bustimes.vehicleMarkers[item.id] = marker;  // make updatePopupContent work
                bustimes.updatePopupContent();
            }
        } else {
            marker = L.marker(latLng, {
                icon: bustimes.getBusIcon(item, isClickedMarker),
                zIndexOffset: 1000,
                item: item
            });
            marker.addTo(map)
                .bindPopup('', {
                    autoPan: false
                })
                .on('popupopen', handlePopupOpen)
                .on('popupclose', handlePopupClose);
        }
        return marker;
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
            var newMarkers = {};
            for (var i = items.length - 1; i >= 0; i--) {
                var item = items[i];
                newMarkers[item.id] = handleVehicle(item);
            }
            // remove old markers
            for (i in bustimes.vehicleMarkers) {
                if (!(i in newMarkers)) {
                    map.removeLayer(bustimes.vehicleMarkers[i]);
                }
            }
            bustimes.vehicleMarkers = newMarkers;
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
