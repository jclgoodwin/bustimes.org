(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest, bustimes
    */

    var container = document.getElementById('map'),
        map = L.map(container);

    bustimes.doTileLayer(map);

    L.control.locate().addTo(map);

    map.fitBounds([[window.EXTENT[1], window.EXTENT[0]], [window.EXTENT[3], window.EXTENT[2]]]);

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

    function handleVehicles(items) {
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

    var loadVehiclesTimeout;

    function loadVehicles() {
        var params = '?operator=' + window.OPERATOR_ID;
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

    loadVehicles();
})();
 