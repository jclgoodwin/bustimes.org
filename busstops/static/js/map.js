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
            var map = L.map('map', {
                    zoomControl: false,
                    dragging: false,
                    touchZoom: false,
                    scrollWheelZoom: false,
                    doubleClickZoom: false,
                    boxZoom: false
                }),
                tileURL = 'https://api.mapbox.com/styles/v1/mapbox/streets-v9/tiles/{z}/{x}/{y}?access_token=pk.eyJ1Ijoiamdvb2R3aW4iLCJhIjoiY2lsODI1OTJqMDAxa3dsbHp6YTIzZW04YiJ9.-gz3QoFQ82JS1uYpaQC7PA',
                attribution = '© <a href="https://www.mapbox.com/map-feedback/">Mapbox</a> | © <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
                pin = L.icon({
                    iconUrl:    '/static/pin.svg',
                    iconSize:   [16, 22],
                    iconAnchor: [8, 22],
                }),
                pinWhite = L.icon({
                    iconUrl:    '/static/pin-white.svg',
                    iconSize:   [16, 22],
                    iconAnchor: [8, 22],
                    popupAnchor: [0, -22],
                }),
                setUpPopup = function(location, label) {
                    var marker = L.marker(location, {icon: pinWhite}).addTo(map).bindPopup(label.innerHTML),
                        a = label.getElementsByTagName('a');
                    if (a.length) {
                        a[0].onmouseover = function() {
                            marker.openPopup();
                        };
                    }
                };

            L.tileLayer(tileURL, {
                tileSize: 512,
                zoomOffset: -1,
                attribution: attribution,
            }).addTo(map);

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

            for (i = labels.length - 1; i >= 0; i -= 1) {
                setUpPopup(mainLocations[i], labels[i], items[i]);
            }
        }

    }

})();
