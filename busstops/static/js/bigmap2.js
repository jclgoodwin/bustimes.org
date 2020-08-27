(function () {
    'use strict';

    var map = L.map('hugemap', {
            minZoom: 8
        }),
        stopsGroup = L.layerGroup();

    map.attributionControl.setPrefix('');

    L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', {
        attribution: '<a href="https://stadiamaps.com/">© Stadia Maps</a> <a href="https://openmaptiles.org/">© OpenMapTiles</a> <a href="https://www.openstreetmap.org/about/">© OpenStreetMap contributors</a>',
    }).addTo(map);

    L.control.locate().addTo(map);

    L.control.layers(null, {
        'Show stops': stopsGroup
    }, {
        collapsed: false
    }).addTo(map);

    var lastStopsReq,
        highWater,
        showStops = true;

    if (localStorage && localStorage.hideStops) {
        showStops = false;
    }

    stopsGroup.on('add', function(e) {
        if (map.getZoom() < 14) {
            map.setZoom(14); // loadStops will be called by moveend handler
        } else if (!showStops) {
            loadStops();
        }
        showStops = true;
        if (localStorage) {
            localStorage.removeItem('hideStops');
        }
    }).on('remove', function(e) {
        showStops = false;
        if (localStorage) {
            localStorage.setItem('hideStops', '1');
        }
    });

    function getTransform(heading, scale) {
        if (heading === null && !scale) {
            return '';
        }
        var transform = 'transform:'
        if (heading !== null) {
            transform += ' rotate(' + heading + 'deg)';
        }
        if (scale) {
            transform += ' scale(1.5)';
        }
        return '-webkit-' + transform + ';' + transform;
    }

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
            html += '<div class="stop-arrow" style="' + getTransform(bearing + 45) + '"></div>';
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
        a.className = 'stop';

        marker.bindPopup(a.outerHTML, {
            autoPan: false
        });

        marker.addTo(stopsGroup);
        newStops[data.properties.url] = marker;
    }

    function loadStops(first) {
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
                if (first) {
                    if (document.referrer && document.referrer.indexOf('/stops/') > -1) {
                        stop = '/stops/' + document.referrer.split('/stops/')[1];
                        stop = newStops[stop];
                        if (stop) {
                            stop.openPopup();
                        }
                    }
                }
                oldStops = newStops;
                newStops = {};
            }
        });
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

    function handleMarkerClick(event) {
        if (clickedMarker) {
            // deselect previous clicked marker
            // (not always covered by popupclose handler, if popup hasn't opened yet)
            var marker = vehicles[clickedMarker];
            if (marker) {
                marker.setIcon(getBusIcon(marker.options.item));
            }
        }

        marker = event.target;
        var item = marker.options.item;

        clickedMarker = item.i;

        marker.setIcon(getBusIcon(item, true));

        var popup = marker.getPopup();
        if (!popup) {
            reqwest({
                url: '/vehicles/locations/' + clickedMarker,
                success: function(content) {
                    marker.options.popupContent = content;
                    marker.bindPopup(content + getPopupContent(item)).openPopup();
                },
                error: function() {
                    marker.options.popupContent = '';
                    marker.bindPopup(getPopupContent(item)).openPopup();
                }
            });

            marker.on('popupclose', function(event) {
                event.target.setIcon(getBusIcon(event.target.options.item));
                clickedMarker = null;
            });
        }

    }

    var vehicles = {};

    function handleVehicle(item) {
        var isClickedMarker = item.i === clickedMarker,
            icon = getBusIcon(item, isClickedMarker),
            latLng = L.latLng(item.l[1], item.l[0]);

        if (item.i in vehicles) {
            var marker = vehicles[item.i];
            marker.setLatLng(latLng);
            marker.setIcon(icon);
            marker.options.item = item;
            var popup = marker.getPopup();
            if (popup) {
                popup.setContent(marker.options.popupContent + getPopupContent(item));
            }
        } else {
            vehicles[item.i] = L.marker(latLng, {
                icon: icon,
                item: item
            }).addTo(map).on('click', handleMarkerClick);
        }
    }

    // websocket

    var socket,
        backoff = 1000,
        firstVehiclesLoad;

    function connect() {
        if (socket && socket.readyState < 2) { // already CONNECTING or OPEN
            return; // no need to reconnect
        }
        var url = (window.location.protocol === 'http:' ? 'ws' : 'wss') + '://' + window.location.host + '/ws/vehicle_positions';
        // url = 'wss://bustimes.org/ws/vehicle_positions';
        socket = new WebSocket(url);

        socket.onopen = function() {
            backoff = 1000;
            firstVehiclesLoad = true;

            var bounds = map.getBounds();
            socket.send(JSON.stringify([
                bounds.getWest(),
                bounds.getSouth(),
                bounds.getEast(),
                bounds.getNorth()
            ]));
        };

        socket.onclose = function() {
            window.setTimeout(connect, backoff);
            backoff += 500;
        };

        socket.onerror = function(event) {
            console.error(event);
        };

        socket.onmessage = function(event) {
            var items = JSON.parse(event.data);
            for (var i = items.length - 1; i >= 0; i--) {
                handleVehicle(items[i]);
            }
            if (firstVehiclesLoad) {
                firstVehiclesLoad = false;
            }
        };
    }

    // update window location hash
    function updateLocation() {
        var latLng = map.getCenter(),
            string = map.getZoom() + '/' + Math.round(latLng.lat * 10000) / 10000 + '/' + Math.round(latLng.lng * 10000) / 10000;

        if (history.replaceState) {
            try {
                history.replaceState(null, null, location.pathname + '#' + string);
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
        var bounds = map.getBounds();

        for (var id in vehicles) {
            var vehicle = vehicles[id];
            if (id !== clickedMarker && !bounds.contains(vehicle.getLatLng())) {
                map.removeLayer(vehicle);
                delete vehicles[id];
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
            if (map.getZoom() < 14) {
                stopsGroup.remove();
                showStops = true;
            } else {
                if (map.getZoom() > 14) {
                    document.getElementById('hugemap').classList.add('zoomed-in');
                } else {
                    document.getElementById('hugemap').classList.remove('zoomed-in');
                }
                stopsGroup.addTo(map);
                loadStops(first);
            }
        }

        updateLocation();

        first = false;
    });

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
})();
