(function () {

    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, loadjs
    */
    var mapContainer = document.getElementById('map');

    if (!mapContainer || !mapContainer.clientWidth) {
        return;
    }

    function getRotation(direction) {
        if (direction == null) {
            return '';
        }
        var rotation = 'transform: rotate(' + direction + 'deg)';
        rotation = '-ms-' + rotation + ';-webkit-' + rotation + ';-moz-' + rotation + ';-o-' + rotation + ';' + rotation;
        return ' style="' + rotation + '"';
    }

    function getIcon(indicator, bearing, active) {
        var className = 'leaflet-div-icon';
        if (active) {
            className += ' active';
        }
        if (indicator) {
            var indicatorParts = indicator.split(' ');
            var firstPart = indicatorParts[0].toLowerCase();
            if (indicatorParts.length === 2 && (firstPart === 'stop' || firstPart === 'bay' || firstPart === 'stand' || firstPart === 'stance')) {
                indicator = indicatorParts[1];
            } else {
                indicator = indicator.slice(0, 3);
            }
        } else {
            indicator = '';
        }
        indicator = '<div class="stop">' + indicator + '</div>';
        if (bearing !== null) {
            indicator += '<div class="arrow"' + getRotation(bearing) + '></div>';
        }
        return L.divIcon({
            iconSize: [20, 20],
            html: indicator,
            popupAnchor: [0, -5],
            className: className
        });
    }

    function setUpMap() {
        var h1 = document.getElementsByTagName('h1')[0],
            items = document.getElementsByTagName('li'),
            i, // transient
            metaElements, // transient
            latLng, // transient
            mainLocations = [], // locations with labels
            labels = []; // label elements

        for (i = items.length - 1; i >= 0; i -= 1) {
            if (items[i].getAttribute('itemtype') === 'https://schema.org/BusStop' && items[i].className != 'OTH' && items[i].className != 'TIP') {
                metaElements = items[i].getElementsByTagName('meta');
                if (metaElements.length) {
                    latLng = [
                        parseFloat(metaElements[0].getAttribute('content')),
                        parseFloat(metaElements[1].getAttribute('content'))
                    ];
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
                    tap: false,
                    scrollWheelZoom: false,
                }),
                tileURL = 'https://maps.bustimes.org/styles/klokantech-basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png',
                setUpPopup = function (location, label) {
                    var marker = L.marker(location, {
                            icon: getIcon(label.getAttribute('data-indicator'), label.getAttribute('data-heading')),
                            riseOnHover: true
                        }).addTo(map).bindPopup(label.innerHTML, {
                            autoPan: false
                        }),
                        a = label.getElementsByTagName('a');
                    if (a.length) {
                        a[0].onmouseover = a[0].ontouchstart = function() {
                            if (!marker.getPopup().isOpen()) {
                                marker.openPopup();
                            }
                        };
                        marker.on('mouseover', function() {
                            marker.openPopup();
                        });
                    }
                };

            map.attributionControl.setPrefix('');

            L.tileLayer(tileURL, {
                attribution: '<a href="https://www.maptiler.com/license/maps/">© MapTiler</a> <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>'
            }).addTo(map);

            if (mainLocations.length > labels.length) { // on a stop point detail page
                i = mainLocations.length - 1;
                L.marker(mainLocations[i], {icon: getIcon(mapContainer.getAttribute('data-indicator'), mapContainer.getAttribute('data-heading'), true)}).addTo(map);
                map.setView(mainLocations[i], 17);
            } else {
                var polyline;
                if (window.geometry) {
                    polyline = L.geoJson(window.geometry, {
                        style: {
                            weight: 2
                        }
                    });
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

    loadjs(['/static/js/bower_components/leaflet/dist/leaflet.js', '/static/js/bower_components/leaflet/dist/leaflet.css'], {
        success: setUpMap
    });

})();
