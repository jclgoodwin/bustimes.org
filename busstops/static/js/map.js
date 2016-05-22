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
            latLng = [],
            locations = [],
            mainLocations = [],
            labels = [];

        for (i = 0; i < items.length; i++) {
            if (items[i].getAttribute('itemtype') === 'https://schema.org/BusStop') {
                metaElements = items[i].getElementsByTagName('meta');
                latLng = [
                    parseFloat(metaElements[0].getAttribute('content')),
                    parseFloat(metaElements[1].getAttribute('content'))
                ];
                if (items[i].className != '') {
                    locations.push(latLng);
                }
                if (items[i].className != 'OTH') {
                    mainLocations.push(latLng);
                    labels.push(items[i]);
                }
            }
        }

        if (!mainLocations.length) {
            metaElements = document.getElementsByTagName('meta');
            for (i = 0; i < metaElements.length; i++) {
                if (metaElements[i].getAttribute('itemprop') === 'latitude') {
                    mainLocations.push([
                        parseFloat(metaElements[i].getAttribute('content')),
                        parseFloat(metaElements[i + 1].getAttribute('content'))
                    ]);
                }
            }
        }

        if (mainLocations.length) {
            var map = L.map('map'),
                attribution = 'Map data &copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors | Map tiles &copy; <a href="https://cartodb.com/attributions#basemaps">CartoDB</a>',
                tileURL = (document.location.protocol === 'https:' ? 'https://cartodb-basemaps-{s}.global.ssl.fastly.net' : 'http://{s}.basemaps.cartocdn.com') + '/light_all/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png',
                pin = L.icon({
                    iconUrl:    '/static/pin.svg',
                    iconSize:   [16, 22],
                    iconAnchor: [8, 22],
                    popupAnchor: [0, -22],
                }),
                setUpPopup = function(location, label) {
                    var marker = L.marker(location, {icon: pin}).addTo(map).bindPopup(label.innerHTML);
                    label.getElementsByTagName('a')[0].onmouseover = function() {
                        marker.openPopup();
                    };
                };

            L.tileLayer(tileURL, {
                attribution: attribution
            }).addTo(map);

            if (mainLocations.length === 1) {
                L.marker(mainLocations[0], {icon: pin}).addTo(map);
                map.setView(mainLocations[0], 17);
            } else {
                for (i = 0; i < mainLocations.length; i++) {
                    setUpPopup(mainLocations[i], labels[i], items[i]);
                }
                if (locations.length) {
                    var polyline = L.polyline(locations, {color: '#000', weight: 2});
                    polyline.addTo(map);
                }
                map.fitBounds((polyline || L.polyline(mainLocations)).getBounds(), {
                    padding: [10, 20]
                });
            }
        }

    }

})();
