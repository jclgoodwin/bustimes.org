(function () {

    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, $
    */

    if (document.getElementById('map').clientWidth > 0) {

        var items = document.getElementsByTagName('li'),
            i,
            metaElements,
            locations = [],
            labels = [];

        for (i = 0; i < items.length; i++) {
            if (items[i].getAttribute('itemtype') === 'https://schema.org/BusStop') {
                metaElements = items[i].getElementsByTagName('meta');
                locations.push([
                    parseFloat(metaElements[0].getAttribute('content')),
                    parseFloat(metaElements[1].getAttribute('content'))
                ]);
                labels.push(items[i].innerHTML);
            }
        }

        if (!locations.length) {
            metaElements = document.getElementsByTagName('meta');
            for (i = 0; i < metaElements.length; i++) {
                if (metaElements[i].getAttribute('itemprop') === 'latitude') {
                    locations.push([
                        parseFloat(metaElements[i].getAttribute('content')),
                        parseFloat(metaElements[i + 1].getAttribute('content'))
                    ]);
                }
            }
        }

        if (locations.length) {
            var map = L.map('map'),
                attribution = 'Map data &copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors | Map tiles &copy; <a href="https://cartodb.com/attributions#basemaps">CartoDB</a>',
                tileURL = (document.location.protocol === 'https:' ? 'https://cartodb-basemaps-{s}.global.ssl.fastly.net' : 'http://{s}.basemaps.cartocdn.com') + '/light_all/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png',
                pin = L.icon({
                    iconUrl:    '/static/pin.svg',
                    iconSize:   [16, 22],
                    iconAnchor: [8, 22],
                    popupAnchor: [0, -22],
                });

            L.tileLayer(tileURL, {
                attribution: attribution
            }).addTo(map);

            if (locations.length === 1) {
                L.marker(locations[0], {icon: pin}).addTo(map);
                map.setView(locations[0], 17);
            } else {
                for (i = 0; i < locations.length; i++) {
                    L.marker(locations[i], {icon: pin}).addTo(map).bindPopup(labels[i]);
                }
                map.fitBounds(L.polyline(locations).getBounds(), {
                    padding: [20, 20]
                });
            }
        }

    }

})();
