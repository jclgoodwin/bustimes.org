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

    bustimes.map = map;

    bustimes.doTileLayer(map);

    L.control.locate().addTo(map);

    map.fitBounds([[window.EXTENT[1], window.EXTENT[0]], [window.EXTENT[3], window.EXTENT[2]]]);

    var loadVehiclesTimeout;

    function loadVehicles() {
        var params = '?operator=' + window.OPERATOR_ID;
        reqwest(
            '/vehicles.json' + params,
            function(data) {
                if (data) {
                    bustimes.handleVehicles(data);
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
 