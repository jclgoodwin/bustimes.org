(function () {
    'use strict';

    /*global
        L, reqwest, bustimes
    */

    var map = L.map('hugemap'),
        stopsGroup = L.layerGroup(),
        vehiclesGroup = L.layerGroup();

    bustimes.doTileLayer(map);

    L.control.locate().addTo(map);

    L.control.layers(null, {
        'Show stops': stopsGroup
    }, {
        collapsed: false
    }).addTo(map);

    var lastStopsReq,
        highWater,
        showStops = true,
        bigStopMarkers,
        bigVehicleMarkers = true;

    if (document.referrer && document.referrer.indexOf('/stops/') > -1) {
        var clickedStopMarker = '/stops/' + document.referrer.split('/stops/')[1];
    } else if (localStorage && localStorage.hideStops) {
        showStops = false;
    }

    stopsGroup.on('add', function() {
        if (map.getZoom() < 13) {
            map.setZoom(13); // loadStops will be called by moveend handler
        } else if (!showStops) {
            loadStops();
        }
        showStops = true;
        if (localStorage) {
            localStorage.removeItem('hideStops');
        }
    }).on('remove', function() {
        if (showStops) {  // box was unchecked (not just a zoom out)
            showStops = false;
            if (localStorage) {
                localStorage.setItem('hideStops', '1');
            }
        }
    });

    vehiclesGroup.addTo(map);

    function getStopIcon(indicator, bearing) {
        var html = '';
        if (indicator) {
            var parts = indicator.split(' ');
            if (parts.length === 2) {
                var firstPart = parts[0].toLowerCase();
                if (firstPart === 'stop' || firstPart === 'bay' || firstPart === 'stand' || firstPart === 'stance' || firstPart === 'gate') {
                    html = parts[1];
                }
            } else if (parts.length === 0 || indicator.length < 3) {
                html = indicator;
            }
        }
        var className = 'stop stop-' + html.length;
        if (bearing !== null) {
            html += '<div class="stop-arrow" style="' + bustimes.getTransform(bearing + 45) + '"></div>';
        } else {
            html += '<div class="stop-arrow no-direction"></div>';
        }
        return L.divIcon({
            iconSize: [16, 16],
            html: html,
            popupAnchor: [0, -4],
            className: className
        });
    }

    var stops = {};

    function handleStop(data) {
        var latLng = L.latLng(data.geometry.coordinates[1], data.geometry.coordinates[0]);
        if (bigStopMarkers) {
            var marker = L.marker(L.latLng(data.geometry.coordinates[1], data.geometry.coordinates[0]), {
                icon: getStopIcon(data.properties.indicator, data.properties.bearing),
                url: data.properties.url
            });
        } else {
            marker = L.circleMarker(latLng, {
                stroke: false,
                fillColor: '#000',
                fillOpacity: .5,
                radius: 3,
                url: data.properties.url
            });
        }
        var a = document.createElement('a');

        a.innerHTML = '<span>' + data.properties.name + '</span><small>' + data.properties.services.join('</small><small>') + '</small>';
        a.href = data.properties.url;

        marker.bindPopup(a.outerHTML, {
            autoPan: false
        })
            .on('popupopen', handleStopPopupOpen)
            .on('popupclose', handleStopPopupClose);

        marker.addTo(stopsGroup);
        stops[data.properties.url] = marker;
    }

    function handleStopPopupOpen(event) {
        var marker = event.target;
        clickedStopMarker = marker.options.url;
    }

    function handleStopPopupClose(event) {
        if (map.hasLayer(event.target)) {
            clickedStopMarker = null;
        }
    }    

    function loadStops() {
        if (lastStopsReq) {
            lastStopsReq.abort();
        }
        bigStopMarkers = (map.getZoom() > 14);
        var bounds = map.getBounds();
        var params = '?ymax=' + bounds.getNorth() + '&xmax=' + bounds.getEast() + '&ymin=' + bounds.getSouth() + '&xmin=' + bounds.getWest();
        if (highWater && highWater.contains(bounds)) {
            if (!bigStopMarkers) {
                return;
            }
        }
        lastStopsReq = reqwest('/stops.json' + params, function(data) {
            if (data && data.features) {
                highWater = bounds;
                stopsGroup.clearLayers();
                stops = {};
                for (var i = data.features.length - 1; i >= 0; i -= 1) {
                    handleStop(data.features[i]);
                }
                if (clickedStopMarker) {
                    var stop = stops[clickedStopMarker];
                    if (stop) {
                        stop.openPopup();
                    }
                }
            }
        });
    }

    var lastVehiclesReq, loadVehiclesTimeout;

    function loadVehicles() {
        if (lastVehiclesReq) {
            lastVehiclesReq.abort();
        }
        if (loadVehiclesTimeout) {
            clearTimeout(loadVehiclesTimeout);
        }
        var bounds = map.getBounds();
        var params = '?ymax=' + bounds.getNorth() + '&xmax=' + bounds.getEast() + '&ymin=' + bounds.getSouth() + '&xmin=' + bounds.getWest();
        lastVehiclesReq = reqwest(
            '/vehicles.json' + params,
            function(data) {
                if (data) {
                    processVehiclesData(data);
                }
                loadVehiclesTimeout = setTimeout(loadVehicles, 15000);
            }
        );
    }

    function processVehiclesData(data) {
        var newMarkers = {};
        var wasZoomedIn = bigVehicleMarkers;
        bigVehicleMarkers = (map.getZoom() > 12) || (data.length < 500);
        if (bigVehicleMarkers !== wasZoomedIn) {
            vehiclesGroup.clearLayers();
            markers = {};
        }
        for (var i = data.length - 1; i >= 0; i--) {
            var item = data[i];
            newMarkers[item.id] = processVehicle(item);
        }
        // remove old markers
        for (i in markers) {
            if (!(i in newMarkers)) {
                vehiclesGroup.removeLayer(markers[i]);
            }
        }
        markers = newMarkers;
    }

    function getVehicleMarker(latLng, legacyItem, isClickedMarker) {
        if (bigVehicleMarkers) {
            var marker = L.marker(latLng, {
                icon: bustimes.getBusIcon(legacyItem, isClickedMarker),
                zIndexOffset: 1000,
            });
        } else {
            marker = L.circleMarker(latLng, {
                stroke: false,
                fillColor: '#111',
                fillOpacity: .6,
                radius: 3,
            });
        }
        marker.addTo(vehiclesGroup)
            .on('popupopen', handlePopupOpen)
            .on('popupclose', handlePopupClose);
        return marker;
    }

    function processVehicle(item) {
        var isClickedMarker = item.id === clickedMarker;
        var latLng = L.latLng(item.coordinates[1], item.coordinates[0]);
        var legacyItem = {
            i: item.id,
            d: item.datetime,
            h: item.heading,
            c: item.vehicle.livery || item.vehicle.css,
            t: item.vehicle.text_colour
        };
        if (item.service) {
            legacyItem.r = item.service.line_name;
        }
        if (item.id in markers) {
            var marker = markers[item.id];  // existing marker
            if (bigVehicleMarkers) {
                marker.setIcon(bustimes.getBusIcon(legacyItem, isClickedMarker));
            }
            marker.setLatLng(latLng);
        } else {
            marker = getVehicleMarker(latLng, legacyItem, isClickedMarker);
            marker.bindPopup('', {
                autoPan: false
            });
        }
        marker.options.legacyItem = legacyItem;
        marker.options.item = item;
        if (isClickedMarker) {
            markers[item.id] = marker;
            marker.openPopup();
            updatePopupContent();
        }
        return marker;

    }

    var clickedMarker, agoTimeout;

    function getPopupContent(item) {
        var now = new Date();
        var then = new Date(item.datetime);
        var ago = Math.round((now.getTime() - then.getTime()) / 1000);

        if (item.service) {
            var content = item.service.line_name;
            if (item.destination) {
                content += ' to ' + item.destination;
            }
            if (item.service.url) {
                content = '<a href="' + item.service.url + '">' + content + '</a>';
            }
        } else {
            content = '';
        }

        content += '<a href="' + item.vehicle.url + '">' + item.vehicle.name + '</a>';

        if (item.vehicle.features) {
            content += item.vehicle.features + '<br>';
        }

        if (item.occupancy) {
            content += item.occupancy + '<br>';
        }

        if (ago >= 1800) {
            content += 'Updated at ' + then.toTimeString().slice(0, 8);
        } else {
            content += '<time datetime="' + item.datetime + '" title="' + then.toTimeString().slice(0, 8) + '">';
            if (ago >= 59) {
                var minutes = Math.round(ago / 60);
                if (minutes === 1) {
                    content += '1 minute';
                } else {
                    content += minutes + ' minutes';
                }
                agoTimeout = setTimeout(updatePopupContent, (61 - ago % 60) * 1000);
            } else {
                if (ago === 1) {
                    content += '1 second';
                } else {
                    content += ago + ' seconds';
                }
                agoTimeout = setTimeout(updatePopupContent, 1000);
            }
            content += ' ago</time>';
        }
        return content;
    }

    function updatePopupContent() {
        if (agoTimeout) {
            clearTimeout(agoTimeout);
        }
        var marker = markers[clickedMarker];
        if (marker) {
            var item = marker.options.item;
            marker.getPopup().setContent((marker.options.popupContent || '') + getPopupContent(item, true));
        }
    }

    function handlePopupOpen(event) {
        var marker = event.target;
        var item = marker.options.item;

        clickedMarker = item.id;
        updatePopupContent();

        if (bigVehicleMarkers) {
            marker.setIcon(bustimes.getBusIcon(marker.options.legacyItem, true));
            marker.setZIndexOffset(2000);
        }
    }

    function handlePopupClose(event) {
        if (map.hasLayer(event.target)) {
            clickedMarker = null;
            if (bigVehicleMarkers) {
                // make the icon small again
                event.target.setIcon(bustimes.getBusIcon(event.target.options.legacyItem));
                event.target.setZIndexOffset(1000);
            }
        }
    }

    var markers = {};

    /*
    function handleVehicle(item) {
        var isClickedMarker = item.i === clickedMarker,
            latLng = L.latLng(item.l[1], item.l[0]),
            marker;

        if (item.i in markers) {
            marker = markers[item.i];
            marker.setLatLng(latLng);
            if (bigVehicleMarkers) {
                marker.setIcon(bustimes.getBusIcon(item, isClickedMarker));
            }
            marker.options.item = item;
            if (isClickedMarker) {
                updatePopupContent();
            }
        } else {
            if (bigVehicleMarkers) {
                marker = L.marker(latLng, {
                    icon: bustimes.getBusIcon(item, isClickedMarker),
                    zIndexOffset: 1000,
                    item: item,
                });
            } else {
                marker = L.circleMarker(latLng, {
                    stroke: false,
                    fillColor: '#111',
                    fillOpacity: .6,
                    radius: 3,
                    item: item,
                });
            }
            markers[item.i] = marker.addTo(vehiclesGroup)
                .bindPopup('', {
                    autoPan: false
                })
                .on('popupopen', handlePopupOpen)
                .on('popupclose', handlePopupClose);

            if (isClickedMarker) {
                marker.openPopup();
            }
        }
    }
    */

    // websocket

    /*
    var socket,
        backoff = 1000,
        newSocket;

    function connect() {
        if (socket && socket.readyState < 2) { // already CONNECTING or OPEN
            return; // no need to reconnect
        }
        var url = (window.location.protocol === 'http:' ? 'ws' : 'wss') + '://' + window.location.host + '/ws/vehicle_positions';
        // url = 'wss://bustimes.org/ws/vehicle_positions';
        socket = new WebSocket(url);

        socket.onopen = function() {
            backoff = 1000;
            newSocket = true;

            var bounds = map.getBounds();
            socket.send(JSON.stringify([
                bounds.getWest(),
                bounds.getSouth(),
                bounds.getEast(),
                bounds.getNorth()
            ]));
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
            var data = JSON.parse(event.data);
            if (newSocket) {
                if (markers) {
                    vehiclesGroup.clearLayers();
                }
                markers = {};
                items = {};
            }
            newSocket = false;
            for (var i = data.length - 1; i >= 0; i--) {
                handleVehicle(data[i]);
                items[data[i].i] = data[i];
            }
        };
    }
    */

    // update window location hash
    function updateLocation() {
        var latLng = map.getCenter(),
            string = map.getZoom() + '/' + Math.round(latLng.lat * 1000) / 1000 + '/' + Math.round(latLng.lng * 1000) / 1000;

        if (history.replaceState) {
            try {
                history.replaceState(null, null, '#' + string);
            } catch (error) {
                // probably SecurityError (document is not fully active)
            }
        }
        if (window.localStorage) {
            try {
                localStorage.setItem('vehicleMap', string);
            } catch (error) {
                // never mind
            }
        }
    }

    var first = true;

    map.on('moveend', function() {
        // var wasZoomedIn = bigVehicleMarkers;
        // bigVehicleMarkers = (map.getZoom() > 10);

        // var bounds = map.getBounds();

        if (!first) {
            loadVehicles();
            /*
            for (var id in markers) {
                var marker = markers[id];
                if (id !== clickedMarker && !bounds.contains(marker.getLatLng())) {
                    vehiclesGroup.removeLayer(marker);
                    delete items[id];
                    delete markers[id];
                }
            }

            if (bigVehicleMarkers && !wasZoomedIn || !bigVehicleMarkers && wasZoomedIn) {
                markers = {};
                vehiclesGroup.clearLayers();
                for (id in items) {
                    handleVehicle(items[id]);
                }
            }

            if (socket && socket.readyState === socket.OPEN) {
                socket.send(JSON.stringify([
                    bounds.getWest(),
                    bounds.getSouth(),
                    bounds.getEast(),
                    bounds.getNorth()
                ]));
            }
            */
        }

        if (showStops) {
            if (map.getZoom() < 13) { // zoomed out
                showStops = false;  // indicate that it wasn't an explicit box uncheck
                stopsGroup.remove();
                showStops = true;
            } else {
                stopsGroup.addTo(map);
                loadStops();
            }
        }

        updateLocation();

        first = false;
    });

    var parts;
    if (location.hash) {
        parts = location.hash.substring(1).split('/');
    } else if (localStorage && localStorage.vehicleMap) {
        parts = localStorage.vehicleMap.split('/');
    }
    if (parts) {
        if (parts.length === 1) {
            parts = parts[0].split(',');
        }
        try {
            if (parts.length === 3) {
                map.setView([parts[1], parts[2]], parts[0]);
            } else {
                map.setView([parts[0], parts[1]], 14);
            }
        } catch (error) {
            // oh well
        }
    }

    if (!map._loaded) {
        map.setView([51.9, 0.9], 9);
    }

    // connect();
    loadVehicles();

    function handleVisibilityChange(event) {
        /*        
        if (event.target.hidden) {
            socket.close(1000);
        } else {
            connect();
        }
        */
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
})();
