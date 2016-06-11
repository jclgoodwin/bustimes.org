(function () {

    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, $
    */

    if (document.getElementById('map').clientWidth > 0) {

        var h1 = document.getElementsByTagName('h1')[0],
            items = document.getElementsByTagName('li'),
            i, // transient
            metaElements, // transient
            latLng, // transient
            locations = [], // locations used to draw a polyline for bus routes
            mainLocations = [], // locations with labels
            labels = []; // label elements

        for (i = items.length - 1; i >= 0; i -= 1) {
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

        // Add the main stop (for the stop point detail page)
        if (h1.getAttribute('itemprop') === 'name') {
            metaElements = document.getElementsByTagName('meta');
            for (i = 0; i < metaElements.length; i++) {
                if (metaElements[i].getAttribute('itemprop') === 'latitude') {
                    mainLocations.push([
                        parseFloat(metaElements[i].getAttribute('content')),
                        parseFloat(metaElements[i + 1].getAttribute('content'))
                    ]);
                    break;
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
                pinWhite = L.icon({
                    iconUrl:    '/static/pin-white.svg',
                    iconSize:   [16, 22],
                    iconAnchor: [8, 22],
                }),
                setUpPopup = function(location, label) {
                    var marker = L.marker(location, {icon: pin}).addTo(map).bindPopup(label.innerHTML),
                        a = label.getElementsByTagName('a');
                    if (a.length) {
                        a[0].onmouseover = function() {
                            marker.openPopup();
                        };
                    }
                };

            L.tileLayer(tileURL, {
                attribution: attribution
            }).addTo(map);

            for (i = labels.length - 1; i >= 0; i -= 1) {
                setUpPopup(mainLocations[i], labels[i], items[i]);
                L.marker(mainLocations[i], {icon: pinWhite}).addTo(map);
            }

            if (mainLocations.length > labels.length) { // on a stop point detail page
                i = mainLocations.length - 1;
                L.marker(mainLocations[i], {icon: pin}).addTo(map);
                map.setView(mainLocations[i], 17);
            } else {
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
