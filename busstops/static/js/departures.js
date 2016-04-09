/*jslint browser: true*/

(function () {
    'use strict';

    var departures = document.getElementById('departures');

    function getDeparturesCallback(response) {
        if (typeof response === 'string') {
            departures.outerHTML = response;
        }
    }

    if (departures) {
        reqwest(window.location.href + '/departures', getDeparturesCallback);
    }
})();
