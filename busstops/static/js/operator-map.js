(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest, bustimes
    */

    var map = L.map('map', {
        tap: false
    });

    bustimes.map = map;

    bustimes.doTileLayer(map);

    L.control.locate().addTo(map);

    var bounds, sorry;

    var loadVehiclesTimeout;

    function loadVehicles() {
        var params = '?operator=' + window.OPERATOR_ID;
        reqwest(
            '/vehicles.json' + params,
            function(data) {
                if (!data) {
                    return;
                }
                bustimes.handleVehicles(data);
                if (data.length) {
                    if (!bounds) {
                        bounds = new L.LatLngBounds();
                        for (var i = data.length - 1; i >= 0; i--) {
                            bounds.extend([data[i].coordinates[1], data[i].coordinates[0]]);
                        }
                        map.fitBounds(bounds);
                    }
                    loadVehiclesTimeout = setTimeout(loadVehicles, 10000);
                } else if (!bounds && !sorry) {
                    sorry = document.createElement('div');
                    sorry.className = 'sorry';
                    sorry.innerHTML = 'Sorry, no buses are tracking at the moment';
                    document.getElementById('map').appendChild(sorry);
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
