(function () {
    'use strict';

    /*global
        L, reqwest, bustimes
    */

    var map = L.map('hugemap', {
            worldCopyJump: true,
            tap: false
        }),
        stopsGroup = L.layerGroup(),
        vehiclesGroup = L.layerGroup();

    bustimes.doTileLayer(map);
    bustimes.popupOptions = {
        autoPan: false
    };

    L.control.locate().addTo(map);

    L.control.layers(null, {
        'Show stops': stopsGroup
    }, {
        collapsed: false
    }).addTo(map);

    var lastStopsReq,
        stopsHighWater,
        showStops = true,
        bigStopMarkers,
        bigVehicleMarkers = true;

    if (document.referrer && document.referrer.indexOf('/stops/') > -1) {
        var clickedStopMarker = '/stops/' + document.referrer.split('/stops/')[1];
    } else {
        try {
            if (localStorage.hideStops) {
                showStops = false;
            }
        } catch (e) {
            // ok
        }
    }

    stopsGroup.on('add', function() {
        if (map.getZoom() < 13) {
            map.setZoom(13); // loadStops will be called by moveend handler
        } else if (!showStops) {
            loadStops();
        }
        showStops = true;
        try {
            localStorage.removeItem('hideStops');
        } catch (e) {
            // ok
        }
    }).on('remove', function() {
        if (showStops) {  // box was unchecked (not just a zoom out)
            showStops = false;
            try {
                localStorage.setItem('hideStops', '1');
            } catch (e) {
                // ok
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
                fillColor: '#333',
                fillOpacity: .5,
                radius: 3,
                url: data.properties.url
            });
        }
        var a = document.createElement('a');

        a.innerHTML = '<span>' + data.properties.name + '</span>';
        if (data.properties.services) {
            a.innerHTML += '<small>' + data.properties.services.join('</small><small>') + '</small>';
        }
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
        var bounds = map.getBounds();
        bigStopMarkers = (map.getZoom() > 14);
        if (stopsHighWater && stopsHighWater.contains(bounds)) {
            if (!bigStopMarkers) {
                return;
            }
        }
        var params = '?ymax=' + round(bounds.getNorth()) + '&xmax=' + round(bounds.getEast()) + '&ymin=' + round(bounds.getSouth()) + '&xmin=' + round(bounds.getWest());
        lastStopsReq = reqwest('/stops.json' + params, function(data) {
            if (data && data.features) {
                stopsHighWater = bounds;
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

    var lastVehiclesReq, loadVehiclesTimeout, vehiclesHighWater;

    function loadVehicles(onMoveEnd) {
        if (lastVehiclesReq) {
            lastVehiclesReq.abort();
        }
        var bounds = map.getBounds();
        if (onMoveEnd && vehiclesHighWater && vehiclesHighWater.contains(bounds) && bigVehicleMarkers) {
            return;
        }
        if (loadVehiclesTimeout) {
            clearTimeout(loadVehiclesTimeout);
        }
        var params = window.location.search;
        if (params) {
            params += '&';
        } else {
            params = '?';
        }
        params += 'ymax=' + round(bounds.getNorth()) + '&xmax=' + round(bounds.getEast()) + '&ymin=' + round(bounds.getSouth()) + '&xmin=' + round(bounds.getWest());
        lastVehiclesReq = reqwest(
            '/vehicles.json' + params,
            function(data) {
                if (data) {
                    vehiclesHighWater = bounds;
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
            bustimes.vehicleMarkers = {};
        }
        for (var i = data.length - 1; i >= 0; i--) {
            var item = data[i];
            newMarkers[item.id] = processVehicle(item);
        }
        // remove old markers
        for (i in bustimes.vehicleMarkers) {
            if (!(i in newMarkers)) {
                vehiclesGroup.removeLayer(bustimes.vehicleMarkers[i]);
            }
        }
        bustimes.vehicleMarkers = newMarkers;
    }

    function getVehicleMarker(latLng, item, isClickedMarker) {
        if (bigVehicleMarkers) {
            var marker = L.marker(latLng, {
                icon: bustimes.getBusIcon(item, isClickedMarker),
                zIndexOffset: 1000,
            });
        } else {
            marker = L.circleMarker(latLng, {
                stroke: false,
                fillColor: '#333',
                fillOpacity: .6,
                radius: 3,
            });
        }
        marker.addTo(vehiclesGroup)
            .bindPopup('', {
                autoPan: false
            })
            .on('popupopen', handlePopupOpen)
            .on('popupclose', handlePopupClose);
        return marker;
    }

    // like handleVehicle in 'maps.js' but with support for varying marker size based on zoom level
    function processVehicle(item) {
        var isClickedMarker = item.id === bustimes.clickedMarker;
        var latLng = L.latLng(item.coordinates[1], item.coordinates[0]);
        if (item.id in bustimes.vehicleMarkers) {
            var marker = bustimes.vehicleMarkers[item.id];  // existing marker
            if (bigVehicleMarkers) {
                marker.setIcon(bustimes.getBusIcon(item, isClickedMarker));
            }
            marker.setLatLng(latLng);
        } else {
            marker = getVehicleMarker(latLng, item, isClickedMarker);
        }
        marker.options.item = item;
        if (isClickedMarker) {
            bustimes.vehicleMarkers[item.id] = marker;  // make updatePopupContent work
            marker.openPopup(); // just in case
            bustimes.updatePopupContent();
        }
        return marker;

    }

    function handlePopupOpen(event) {
        var marker = event.target;
        var item = marker.options.item;

        bustimes.clickedMarker = item.id;
        bustimes.updatePopupContent();

        if (bigVehicleMarkers) {
            marker.setIcon(bustimes.getBusIcon(item, true));
            marker.setZIndexOffset(2000);
        }
    }

    function handlePopupClose(event) {
        if (map.hasLayer(event.target)) {
            bustimes.clickedMarker = null;
            if (bigVehicleMarkers) {
                // make the icon small again
                event.target.setIcon(bustimes.getBusIcon(event.target.options.item));
                event.target.setZIndexOffset(1000);
            }
        }
    }

    function round(number) {
        return Math.round(number * 1000) / 1000;
    }

    // update window location hash
    function updateLocation() {
        var latLng = map.getCenter(),
            string = map.getZoom() + '/' + round(latLng.lat) + '/' + round(latLng.lng);

        if (history.replaceState) {
            try {
                history.replaceState(null, null, '#' + string);
            } catch (e) {
                // probably SecurityError (document is not fully active)
            }
        }
        try {
            localStorage.setItem('vehicleMap', string);
        } catch (e) {
            // ok
        }
    }

    var first = true;

    map.on('moveend', function() {
        if (!first) {
            loadVehicles(true);
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
    } else {
        try {
            if (localStorage.vehicleMap) {
                parts = localStorage.vehicleMap.split('/');
            }
        } catch (e) {
            // ok
        }
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
        } catch (e) {
            // oh well
        }
    }

    if (!map._loaded) {
        map.setView([51.9, 0.9], 9);
    }

    loadVehicles();

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
})();
