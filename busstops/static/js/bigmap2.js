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
        zoomedIn = true;

    if (document.referrer && document.referrer.indexOf('/stops/') > -1) {
        var referrerStop = '/stops/' + document.referrer.split('/stops/')[1];
    } else if (localStorage && localStorage.hideStops) {
        showStops = false;
    }

    stopsGroup.on('add', function() {
        if (map.getZoom() < 14) {
            map.setZoom(14); // loadStops will be called by moveend handler
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

    var oldStops = {},
        newStops = {};

    function handleStop(data) {
        if (data.properties.url in oldStops) {
            var marker = oldStops[data.properties.url];
            newStops[data.properties.url] = marker;
            return;
        }

        var a = document.createElement('a');
        marker = L.marker(L.latLng(data.geometry.coordinates[1], data.geometry.coordinates[0]), {
            icon: getStopIcon(data.properties.indicator, data.properties.bearing)
        });

        a.innerHTML = '<span>' + data.properties.name + '</span><small>' + data.properties.services.join('</small><small>') + '</small>';
        a.href = data.properties.url;

        marker.bindPopup(a.outerHTML, {
            autoPan: false
        });

        marker.addTo(stopsGroup);
        newStops[data.properties.url] = marker;
    }

    function loadStops() {
        var bounds = map.getBounds();
        var params = '?ymax=' + bounds.getNorth() + '&xmax=' + bounds.getEast() + '&ymin=' + bounds.getSouth() + '&xmin=' + bounds.getWest();

        if (lastStopsReq) {
            lastStopsReq.abort();
        }
        if (highWater && highWater.contains(bounds)) {
            return;
        }
        lastStopsReq = reqwest('/stops.json' + params, function(data) {
            if (data && data.features) {
                highWater = bounds;
                for (var i = data.features.length - 1; i >= 0; i -= 1) {
                    handleStop(data.features[i]);
                }
                for (var stop in oldStops) {
                    if (!(stop in newStops)) {
                        stopsGroup.removeLayer(oldStops[stop]);
                    }
                }
                if (referrerStop) {
                    stop = newStops[referrerStop];
                    if (stop) {
                        stop.openPopup();
                    }
                }
                oldStops = newStops;
                newStops = {};
            }
        });
    }

    var clickedMarker, agoTimeout;

    function getPopupContent(item) {
        var content = bustimes.getDelay(item);
        var now = new Date();
        var then = new Date(item.d);
        var ago = Math.round((now.getTime() - then.getTime()) / 1000);

        if (ago >= 1800) {
            content += 'Updated at ' + then.toTimeString().slice(0, 8);
        } else {
            content += '<time datetime="' + item.d + '" title="' + then.toTimeString().slice(0, 8) + '">';
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

        clickedMarker = item.i;
        updatePopupContent();

        if (zoomedIn) {
            marker.setIcon(bustimes.getBusIcon(item, true));
            marker.setZIndexOffset(2000);
        }

        reqwest({
            url: '/vehicles/locations/' + item.i,
            success: function(content) {
                marker.options.popupContent = content;
                updatePopupContent();
            }
        });
    }

    function handlePopupClose(event) {
        if (map.hasLayer(event.target)) {
            clickedMarker = null;
            if (zoomedIn) {
                // make the icon small again
                event.target.setIcon(bustimes.getBusIcon(event.target.options.item));
                event.target.setZIndexOffset(1000);
            }
        }
    }

    var markers, items;

    function handleVehicle(item) {
        var isClickedMarker = item.i === clickedMarker,
            latLng = L.latLng(item.l[1], item.l[0]),
            marker;

        if (item.i in markers) {
            marker = markers[item.i];
            marker.setLatLng(latLng);
            if (zoomedIn) {
                marker.setIcon(bustimes.getBusIcon(item, isClickedMarker));
            }
            marker.options.item = item;
            if (isClickedMarker) {
                updatePopupContent();
            }
        } else {
            if (zoomedIn) {
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

    // websocket

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

    // update window location hash
    function updateLocation() {
        var latLng = map.getCenter(),
            string = map.getZoom() + '/' + Math.round(latLng.lat * 10000) / 10000 + '/' + Math.round(latLng.lng * 10000) / 10000;

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
        var wasZoomedIn = zoomedIn;
        zoomedIn = (map.getZoom() > 10);

        var bounds = map.getBounds();

        for (var id in markers) {
            var marker = markers[id];
            if (id !== clickedMarker && !bounds.contains(marker.getLatLng())) {
                vehiclesGroup.removeLayer(marker);
                delete items[id];
                delete markers[id];
            }
        }

        if (zoomedIn && !wasZoomedIn || !zoomedIn && wasZoomedIn) {
            markers = {};
            vehiclesGroup.clearLayers();
            for (id in items) {
                handleVehicle(items[id]);
            }
        }

        if (!first && socket && socket.readyState === socket.OPEN) {
            socket.send(JSON.stringify([
                bounds.getWest(),
                bounds.getSouth(),
                bounds.getEast(),
                bounds.getNorth()
            ]));
        }

        if (showStops) {
            if (map.getZoom() < 14) { // zoomed out
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

    // zoomedIn = (map.getZoom() > 10);

    connect();

    function handleVisibilityChange(event) {
        if (event.target.hidden) {
            socket.close(1000);
        } else {
            connect();
        }
    }

    if (document.addEventListener) {
        document.addEventListener('visibilitychange', handleVisibilityChange);
    }
})();
