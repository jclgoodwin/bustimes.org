(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest
    */

    var container = document.getElementById('map'),
        map = L.map(container),
        vehicles = {},
        vehicleMarkers = {};

    L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', {
        attribution: '<a href="https://stadiamaps.com/">© Stadia Maps</a> <a href="https://openmaptiles.org/">© OpenMapTiles</a> <a href="https://www.openstreetmap.org/about/">© OpenStreetMap contributors</a>',
    }).addTo(map);

    map.fitBounds([[window.EXTENT[1], window.EXTENT[0]], [window.EXTENT[3], window.EXTENT[2]]]);

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

    function getBusIcon(item, active) {
        var heading = item.h;
        if (heading !== null) {
            var arrow = '<div class="arrow" style="' + getTransform(heading, active) + '"></div>';
            if (heading < 180) {
                heading -= 90;
            } else {
                heading -= 270;
            }
        }
        var className = 'bus';
        if (active) {
            className += ' selected';
        }
        if (item.c) {
            var style = 'background:' + item.c;
            className += ' coloured';
            if (item.t) {
                className += ' white-text';
            }
            style += ';';
        } else {
            style = '';
        }
        style += getTransform(heading, active);
        var html = '<div class="' + className + '" style="' + style + '">';
        if (item.r) {
            html += item.r;
        }
        html += '</div>';
        if (arrow) {
            html += arrow;
        }
        return L.divIcon({
            iconSize: [20, 20],
            html: html,
            popupAnchor: [0, -5],
        });
    }

    var clickedMarker;

    function getPopupContent(item) {
        var delta = '';
        if (item.e === 0) {
            delta = 'On time<br>';
        } else if (item.e) {
            delta += 'About ';
            if (item.e > 0) {
                delta += item.e;
            } else {
                delta += item.e * -1;
            }
            delta += ' minute';
            if (item.e !== 1 && item.e !== -1) {
                delta += 's';
            }
            if (item.e > 0) {
                delta += ' early';
            } else {
                delta += ' late';
            }
            delta += '<br>';
        }

        var datetime = new Date(item.d);

        return delta + 'Updated at ' + datetime.toTimeString().slice(0, 5);
    }


    function handlePopupOpen(event) {
        var marker = event.target;
        var item = marker.options.item;

        clickedMarker = item.i;

        marker.setIcon(getBusIcon(item, true));
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
            event.target.setIcon(getBusIcon(event.target.options.item));
            event.target.setZIndexOffset(1000);
        }
    }

    function handleVehicle(item) {
        if (map) {
            var isClickedMarker = item.i === clickedMarker,
                icon = getBusIcon(item, isClickedMarker),
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
 