(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest, Cowboy
    */

    var map = L.map('hugemap', {
            minZoom: 10
        }),
        tileURL = 'https://maps.bustimes.org/styles/klokantech-basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png',
        statusBar = L.control({
            position: 'bottomleft'
        }),
        lastVehiclesReq,
        lastStopsReq,
        timeout,
        oldVehicles = {},
        newVehicles = {},
        oldStops = {},
        newStops = {},
        stopsGroup = L.layerGroup(),
        vehiclesGroup = L.layerGroup(),
        highWater;

    stopsGroup.addTo(map);
    vehiclesGroup.addTo(map);

    map.attributionControl.setPrefix('');

    L.tileLayer(tileURL, {
        attribution: '<a href="https://www.maptiler.com/copyright/">© MapTiler</a> <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>'
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
        return '-ms-' + rotation + ';-webkit-' + rotation + ';-moz-' + rotation + ';-o-' + rotation + ';' + rotation;
    }

    function getBusIcon(service, direction, livery, textColour) {
        if (direction === null) {
            var html = '';
        } else {
            html = '<div class="arrow" style="' + getRotation(direction) + '"></div>';
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
        html += '<div class="' + className + '" style="' + style + '">';
        if (service) {
            html += service.line_name;
        }
        html += '</div>';
        return L.divIcon({
            iconSize: [20, 20],
            html: html,
            popupAnchor: [0, -5],
        });
    }

    function getStopIcon(indicator, bearing) {
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
            indicator += '<div class="arrow" style="' + getRotation(bearing) + '"></div>';
        }
        return L.divIcon({
            iconSize: [20, 20],
            html: indicator,
            popupAnchor: [0, -5],
            className: className
        });
    }

    function handleVehicle(data) {
        if (data.properties.vehicle.url in oldVehicles) {
            var marker = oldVehicles[data.properties.vehicle.url];
            newVehicles[data.properties.vehicle.url] = marker;
            if (marker.datetime === data.properties.datetime) {
                return;
            }
        }

        var icon = getBusIcon(data.properties.service, data.properties.direction, data.properties.vehicle.livery, data.properties.vehicle.text_colour),
            latLng = L.latLng(data.geometry.coordinates[1], data.geometry.coordinates[0]);

        if (marker) {
            marker.setLatLng(latLng);
            marker.setIcon(icon);
        } else {
            marker = L.marker(latLng, {
                icon: icon
            });
            marker.addTo(vehiclesGroup);
            newVehicles[data.properties.vehicle.url] = marker;
        }
        marker.datetime = data.properties.datetime;

        var popup = '';
        if (data.properties.service) {
            if (data.properties.service.url) {
                popup = '<a href="' + data.properties.service.url + '">' + data.properties.service.line_name + '</a>';
            } else {
                popup = data.properties.service.line_name;
            }
        }
        if (data.properties.destination) {
            popup += ' to ' + data.properties.destination;
        }

        if (data.properties.operator) {
            if (popup) {
                popup += '<br>';
            }
            popup += data.properties.operator + '<br>';
        }

        if (data.properties.vehicle) {
            popup += '<a href="' + data.properties.vehicle.url + '">' + data.properties.vehicle.name + '</a>';
            if (data.properties.vehicle.type) {
                popup += ' - ' + data.properties.vehicle.type;
            }
            if (data.properties.vehicle.notes) {
                popup += ' - ' + data.properties.vehicle.notes;
            }
            popup += '<br>';
        }

        if (data.properties.delta === 0) {
            popup += 'On time<br>';
        } else if (data.properties.delta) {
            popup += 'About ';
            if (data.properties.delta > 0) {
                popup += data.properties.delta;
            } else {
                popup += data.properties.delta * -1;
            }
            popup += ' minute';
            if (data.properties.delta !== 1 && data.properties.delta !== -1) {
                popup += 's';
            }
            if (data.properties.delta > 0) {
                popup += ' early';
            } else {
                popup += ' late';
            }
            popup += '<br>';
        }

        var dateTime = new Date(data.properties.datetime);
        popup += 'Updated at ' + dateTime.toTimeString().slice(0, 5);

        if (data.properties.source === 75 && data.properties.service && data.properties.service.url) {
            popup += '<br>(Updates if someone views<br><a href="' + data.properties.service.url + '">the ' + data.properties.service.line_name + ' page</a>)';
        }

        marker.bindPopup(popup);
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

        a.innerHTML = data.properties.name;
        a.href = data.properties.url;

        marker.bindPopup(a.outerHTML, {
            autoPan: false
        });

        marker.addTo(stopsGroup);
        newStops[data.properties.url] = marker;
    }

    function processVehiclesData(data) {
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
        statusBar.getContainer().innerHTML = '';
    }

    function processStopsData(data) {
        for (var i = data.features.length - 1; i >= 0; i -= 1) {
            handleStop(data.features[i]);
        }
        for (var stop in oldStops) {
            if (!(stop in newStops)) {
                stopsGroup.removeLayer(oldStops[stop]);
            }
        }
        oldStops = newStops;
        newStops = {};
    }

    // load vehicles, and possibly stops
    function load(map, statusBar, stops) {
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
                }, 10000);
            }
        );

        if (stops) {
            if (lastStopsReq) {
                lastStopsReq.abort();
            }
            if (map.getZoom() < 15) {
                stopsGroup.clearLayers();
                highWater = null;
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
        load(map, statusBar, true);

        var latLng = event.target.getCenter(),
            string = event.target.getZoom() + '/' + Math.round(latLng.lat * 10000) / 10000 + '/' + Math.round(latLng.lng * 10000) / 10000;

        if (history.replaceState) {
            history.replaceState(null, null, location.pathname + '#' + string);
        }
        if (window.localStorage) {
            localStorage.setItem('vehicleMap', string);
        }
    }

    map.on('moveend', Cowboy.debounce(500, handleMoveEnd));

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
    } else if (localStorage.vehicleMap) {
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

    document.addEventListener('visibilitychange', handleVisibilityChange);

    var locateButton = L.control();

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
