(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest
    */

    var map = L.map('hugemap', {
            minZoom: 8
        }),
        statusBar = L.control(),
        lastVehiclesReq,
        lastStopsReq,
        timeout,
        oldVehicles = {},
        newVehicles = {},
        oldStops = {},
        newStops = {},
        stopsGroup = L.layerGroup(),
        vehiclesGroup = L.layerGroup(),
        highWater,
        first = true;

    stopsGroup.addTo(map);
    vehiclesGroup.addTo(map);

    map.attributionControl.setPrefix('');

    L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', {
        attribution: '<a href="https://stadiamaps.com/">© Stadia Maps</a> <a href="https://openmaptiles.org/">© OpenMapTiles</a> <a href="https://www.openstreetmap.org/about/">© OpenStreetMap contributors</a>',
    }).addTo(map);

    statusBar.onAdd = function () {
        var div = L.DomUtil.create('div', 'hugemap-status');
        return div;
    };
    statusBar.addTo(map);

    function getRotation(direction) {
        if (direction === null) {
            return '';
        }
        var rotation = 'transform: rotate(' + direction + 'deg)';
        return '-webkit-' + rotation + ';' + rotation;
    }

    function getBusIcon(service, direction, livery, textColour) {
        if (direction !== null) {
            var arrow = '<div class="arrow" style="' + getRotation(direction) + '"></div>';
            if (direction < 180) {
                direction -= 90;
            } else {
                direction -= 270;
            }
        }
        var className = 'bus';
        if (livery) {
            var style = 'background:' + livery;
            className += ' coloured';
            if (textColour) {
                className += ' white-text';
            }
            style += ';';
        } else {
            style = '';
        }
        style += getRotation(direction);
        var html = '<div class="' + className + '" style="' + style + '">';
        if (service) {
            html += service.line_name;
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
            html += '<div class="stop-arrow" style="' + getRotation(bearing + 45) + '"></div>';
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

    function getPopupContent(props) {
        var popup = '';
        if (props.service) {
            if (props.service.url) {
                popup = '<a href="' + props.service.url + '">' + props.service.line_name + '</a>';
            } else {
                popup = props.service.line_name;
            }
        }
        if (props.destination) {
            if (props.destination.indexOf(' to ') === -1) {
                popup += ' to ';
            }
            popup += props.destination;
        }

        if (props.operator) {
            if (popup) {
                popup += '<br>';
            }
            popup += props.operator + '<br>';
        }

        if (props.vehicle) {
            popup += '<a href="' + props.vehicle.url + '">' + props.vehicle.name + '</a><br>';
        }

        if (props.vehicle.decker) {
            var features = 'Double-decker';
            if (props.vehicle.coach) {
                features += ' coach';
            }
        } else if (props.vehicle.coach) {
            features = 'Coach';
        } else {
            features = '';
        }

        if (props.vehicle.features && props.vehicle.features.length) {
            if (features) {
                features += '<br>';
            }
            features += props.vehicle.features.join(', ');
        }

        if (features) {
            popup += features + '<br>';
        }



        if (props.delta === 0) {
            popup += 'On time<br>';
        } else if (props.delta) {
            popup += 'About ';
            if (props.delta > 0) {
                popup += props.delta;
            } else {
                popup += props.delta * -1;
            }
            popup += ' minute';
            if (props.delta !== 1 && props.delta !== -1) {
                popup += 's';
            }
            if (props.delta > 0) {
                popup += ' early';
            } else {
                popup += ' late';
            }
            popup += '<br>';
        }

        var then = new Date(props.datetime);
        var now = new Date();
        var ago = Math.round((now.getTime() - then.getTime()) / 1000);
        var minutes = Math.round(ago / 60);

        if (minutes) {
            if (minutes === 1) {
                popup += '1 minute ago';
            } else {
                popup += minutes + ' minutes ago';
            }
        } else {
            if (ago === 1) {
                popup += '1 second ago';
            } else {
                popup += ago + ' seconds ago';
            }
        }

        if ((props.source === 75 || props.source === 79 || props.source === 86) && props.service && props.service.url) {
            popup += '<br>(Updates if someone views<br><a href="' + props.service.url + '">the ' + props.service.line_name + ' page</a>)';
        }

        return popup;
    }

    var openPopupMarker,
        agoTimeout;

    function updatePopupContent() {
        if (agoTimeout) {
            clearTimeout(agoTimeout);
        }
        if (openPopupMarker.isPopupOpen()) {
            openPopupMarker.getPopup().setContent(getPopupContent(openPopupMarker.props));
            agoTimeout = setTimeout(updatePopupContent, 30000);
        }
    }

    function handleVehicleClick(event) {
        openPopupMarker = event.target;
        var popup = openPopupMarker.getPopup();
        if (popup) {
            updatePopupContent();
        } else {
            openPopupMarker.bindPopup(getPopupContent(openPopupMarker.props)).openPopup();
            agoTimeout = setTimeout(updatePopupContent, 30000);
        }
    }

    function handleVehicle(data) {
        var props = data.properties;

        if (props.vehicle.url in oldVehicles) {
            var marker = oldVehicles[props.vehicle.url];
            newVehicles[props.vehicle.url] = marker;
            if (marker.props.datetime === props.datetime) {
                return;
            }
        }

        var icon = getBusIcon(props.service, props.direction, props.vehicle.livery, props.vehicle.text_colour),
            latLng = L.latLng(data.geometry.coordinates[1], data.geometry.coordinates[0]);

        if (marker) {
            marker.setLatLng(latLng);
            marker.setIcon(icon);
        } else {
            marker = L.marker(latLng, {
                icon: icon,
                zIndexOffset: 1000
            });
            marker.addTo(vehiclesGroup);
            newVehicles[props.vehicle.url] = marker;
        }
        marker.props = props;
        marker.on('click', handleVehicleClick);
    }

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

    function processVehiclesData(data) {
        if (data && data.features) {
            for (var i = data.features.length - 1; i >= 0; i -= 1) {
                handleVehicle(data.features[i]);
            }
            for (var vehicle in oldVehicles) {
                if (!(vehicle in newVehicles)) {
                    vehiclesGroup.removeLayer(oldVehicles[vehicle]);
                }
            }
            oldVehicles = newVehicles;
            newVehicles = {};
            if (map.getZoom() < 15) {
                statusBar.getContainer().innerHTML = 'Zoom in to see stops';
            } else {
                statusBar.getContainer().innerHTML = '';
            }
        }
        if (openPopupMarker) {
            updatePopupContent();
        }
    }

    function processStopsData(data) {
        if (data && data.features) {
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
                first = false;
            }
            oldStops = newStops;
            newStops = {};
        }
    }

    // load vehicles, and possibly stops
    function load(map, statusBar, stops) {
        // if (map.getZoom() < 10) {
        //     statusBar.getContainer().innerHTML = 'Zoom in to see buses and stops';
        //     return;
        // }
        statusBar.getContainer().innerHTML = 'Loading\u2026';
        var bounds = map.getBounds();
        var params = '?ymax=' + bounds.getNorth() + '&xmax=' + bounds.getEast() + '&ymin=' + bounds.getSouth() + '&xmin=' + bounds.getWest();

        if (lastVehiclesReq) {
            lastVehiclesReq.abort();
        }
        lastVehiclesReq = reqwest(
            '/vehicles.json' + params,
            function(data) {
                if (data) {
                    processVehiclesData(data);
                }
                timeout = setTimeout(function() {
                    load(map, statusBar, false);
                }, 15000);
            }
        );

        if (stops) {
            if (lastStopsReq) {
                lastStopsReq.abort();
            }
            if (map.getZoom() < 15) {
                // zoomed out too far to show stops
                stopsGroup.clearLayers();
                oldStops = {};
                highWater = null;
                first = false;
                return;
            }
            if (highWater && highWater.contains(bounds)) {
                return;
            }
            lastStopsReq = reqwest('/stops.json' + params, processStopsData);
            highWater = bounds;
        }
    }

    function handleMoveEnd(event) {
        clearTimeout(timeout);

        loadOnMoveEnd(map, statusBar, true);
        updateLocation(event);
    }

    var loadOnMoveEnd = debounce(load, 700);

    function updateLocation(event) {
        var latLng = event.target.getCenter(),
            string = event.target.getZoom() + '/' + Math.round(latLng.lat * 10000) / 10000 + '/' + Math.round(latLng.lng * 10000) / 10000;

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

    function debounce(func, wait, immediate) {
        var timeout;
        return function() {
            var context = this, args = arguments;
            var later = function() {
                timeout = null;
                if (!immediate) func.apply(context, args);
            };
            var callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(context, args);
        };
    }

    map.on('moveend', handleMoveEnd);

    window.onhashchange = function(event) {
        var parts = event.target.location.hash.substr(1).split('/');

        if (parts.length == 3) {
            try {
                map.setView([parts[1], parts[2]], parts[0]);
            } catch (error) {
                // caught!
            }
        }
    };

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
                map.setView([parts[0], parts[1]], 15);
            }
        } catch (error) {
            // oh well
        }
    }
    if (!map._loaded) {
        map.setView([51.9, 0.9], 9);
    }

    function handleVisibilityChange(event) {
        if (event.target.hidden) {
            clearTimeout(timeout);
        } else {
            load(map, statusBar, false);
        }
    }

    if (document.addEventListener) {
        document.addEventListener('visibilitychange', handleVisibilityChange);
    }

    var locateButton = L.control({
        position: 'topleft'
    });

    locateButton.onAdd = function(map) {
        var div = document.createElement('div');
        div.className = 'leaflet-bar';
        var a = document.createElement('a');
        a.href = '#';
        a.title = 'Find my location';
        a.setAttribute('role', 'button');
        var img = document.createElement('img');
        img.alt = 'Locate';
        img.width = 16;
        img.height = 16;
        img.src = '/static/locate.png';
        a.appendChild(img);
        div.appendChild(a);

        function locate() {
            img.className = 'working';
            map.locate({setView: true});
            return false;
        }

        function located() {
            img.className = '';
        }
        a.onclick = locate;

        map.on('locationfound', located);
        map.on('locationerror', located);

        return div;
    };

    locateButton.addTo(map);

    load(map, statusBar, true);
})();
