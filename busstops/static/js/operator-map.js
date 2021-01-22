(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest, bustimes
    */

    var container = document.getElementById('map'),
        map = L.map(container),
        vehicles = {},
        vehicleMarkers = {};

    bustimes.doTileLayer(map);

    map.fitBounds([[window.EXTENT[1], window.EXTENT[0]], [window.EXTENT[3], window.EXTENT[2]]]);

    var clickedMarker;

    function getPopupContent(item) {
        var delta = bustimes.getDelay(item);

        var datetime = new Date(item.d);

        return delta + 'Updated at ' + datetime.toTimeString().slice(0, 5);
    }


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
                marker.getPopup().setContent(content + getPopupContent(item));
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
                marker.getPopup().setContent((marker.options.popupContent || '') + getPopupContent(item));
            } else {
                vehicleMarkers[item.i] = L.marker(latLng, {
                    icon: icon,
                    item: item,
                    zIndexOffset: 1000
                }).addTo(map)
                    .bindPopup(getPopupContent(item))
                    .on('popupopen', handlePopupOpen)
                    .on('popupclose', handlePopupClose);

            }
        }
        vehicles[item.i] = item;
    }

    // websocket

    var socket,
        backoff = 1000,
        newSocket;

    function connect() {
        if (socket && socket.readyState < 2) { // already CONNECTING or OPEN
            return; // no need to reconnect
        }
        var protocol = (window.location.protocol === 'http:' ? 'ws' : 'wss');
        var host = window.location.host;
        // protocol = 'wss';
        // host = 'bustimes.org';
        var url = protocol + '://' + host + '/ws/vehicle_positions/operators/' + window.OPERATOR_ID;
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

    connect();

    // services.addTo(map);
})();
 