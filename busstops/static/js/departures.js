/*jslint browser: true*/

(function () {
    'use strict';

    var departures = document.getElementById('departures');

    function getDeparturesURL() {
       var metaElements = document.getElementsByTagName('link');
       for (var i = metaElements.length - 1; i >= 0; i--) {
           if ('canonical' === metaElements[i].rel) {
               return metaElements[i].href + '/departures';
           }
       }
    }

    function getDeparturesCallback(response) {
        if (typeof response === 'string') {
            departures.outerHTML = response;
        }
    }

    if (departures) {
        reqwest(getDeparturesURL(), getDeparturesCallback);
    }
})();
