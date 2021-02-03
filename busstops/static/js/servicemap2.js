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
        button = busesOnline.getElementsByTagName('a')[0],
        vehicles = {},
        vehicleMarkers = {};

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
        connect();
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
            var html = '<div class="stop-arrow" style="' + getTransform(feature.properties.bearing + 45) + '"></div>';
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

        for (var id in vehicles) {
            handleVehicle(vehicles[id]);
        }
    }

    function getTransform(heading, scale) {
        if (heading === null && !scale) {
            return '';
        }
        var transform = 'transform:';
        if (heading !== null) {
            transform += ' rotate(' + heading + 'deg)';
        }
        if (scale) {
            transform += ' scale(1.5)';
        }
        return '-webkit-' + transform + ';' + transform;
    }


    var clickedMarker;

    function handlePopupOpen(event) {
        var marker = event.target;
        var item = marker.options.item;

        clickedMarker = item.i;

        marker.setIcon(bustimes.getBusIcon(item, true));
        marker.setZIndexOffset(2000);

        reqwest({
            url: '/vehicles/locations/' + item.i,
            success: function(content) {
                marker.options.popupContent = content;
                marker.getPopup().setContent(content + bustimes.getPopupContent(item));
            }
        });
    }

    function handlePopupClose(event) {
        if (map.hasLayer(event.target)) {
            clickedMarker = null;
            // make the icon small again
            event.target.setIcon(bustimes.getBusIcon(event.target.options.item));
            event.target.setZIndexOffset(1000);
        }
    }

    function handleVehicle(item) {
        if (map) {
            var isClickedMarker = item.i === clickedMarker,
                icon = bustimes.getBusIcon(item, isClickedMarker),
                latLng = L.latLng(item.l[1], item.l[0]);

            if (item.i in vehicleMarkers) {
                var marker = vehicleMarkers[item.i];
                marker.setLatLng(latLng);
                marker.setIcon(icon);
                marker.options.item = item;
                marker.getPopup().setContent((marker.options.popupContent || '') + bustimes.getPopupContent(item));
            } else {
                vehicleMarkers[item.i] = L.marker(latLng, {
                    icon: icon,
                    item: item,
                    zIndexOffset: 1000
                }).addTo(map)
                    .bindPopup(bustimes.getPopupContent(item))
                    .on('popupopen', handlePopupOpen)
                    .on('popupclose', handlePopupClose);

            }
        }
        vehicles[item.i] = item;
    }

    var busesOnlineCount;

    // websocket

    var socket,
        backoff = 1000,
        newSocket;

    function connect() {
        if (!window.SERVICE_TRACKING) {
            return;
        }

        if (socket && socket.readyState < 2) { // already CONNECTING or OPEN
            return; // no need to reconnect
        }
        var url = (window.location.protocol === 'http:' ? 'ws' : 'wss') + '://' + window.location.host + '/ws/vehicle_positions/services/' + service;
        socket = new WebSocket(url);

        socket.onopen = function() {
            backoff = 1000;
            newSocket = true;
        };

        socket.onclose = function(event) {
            if (event.code > 1000) {  // not 'normal closure'
                window.setTimeout(connect, backoff);
                backoff += 500;
            }
        };

        socket.onerror = function(event) {
            console.error(event);
        };

        socket.onmessage = function(event) {
            var items = JSON.parse(event.data);

            if (!busesOnlineCount) { // first load
                if (items.length) {
                    busesOnlineCount = document.createElement('span');
                    busesOnline.appendChild(busesOnlineCount);
                    if (items.length === 1) {
                        busesOnlineCount.innerHTML = 'Tracking 1 bus';
                    } else {
                        busesOnlineCount.innerHTML = 'Tracking ' + items.length + ' buses';
                    }
                } else {
                    if (!map) {
                        socket.close(1000);
                    }
                    return;
                }
            }

            if (newSocket) {
                var newVehicles = {};
            }
            newSocket = false;
            for (var i = items.length - 1; i >= 0; i--) {
                handleVehicle(items[i]);
                if (newVehicles) {
                    newVehicles[items[i].i] = true;
                }
            }
            if (newVehicles) {
                for (var id in vehicles) {
                    if (!(id in newVehicles)) {
                        if (map) {
                            map.removeLayer(vehicles[id]);
                            delete vehicleMarkers[id];
                        }
                        delete vehicles[id];
                    }
                }
            }
        };
    }

    function closeMap() {
        container.className = container.className.replace(' expanded', '');
        document.body.style.overflow = '';
        setLocationHash('');

        if (socket) {
            socket.close(1000);
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

    connect();

    function handleVisibilityChange(event) {
        if (event.target.hidden) {
            if (socket) {
                socket.close(1000);
            }
        } else {
            connect();
        }
    }

    if (document.addEventListener) {
        document.addEventListener('visibilitychange', handleVisibilityChange);
    }

    if (window.location.hash === '#map') {
        openMap();
    }

})();
