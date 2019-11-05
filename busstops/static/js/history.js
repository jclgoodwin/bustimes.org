(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest
    */

    var map,
        mapContainer = document.getElementById('journey-overlay'),
        layerGroup = L.layerGroup(),
        tileURL = 'https://maps.bustimes.org/styles/klokantech-basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png';

    function getMarker(latLng, direction) {
        direction = (direction || 0) - 135;
        return L.marker(latLng, {
            icon: L.divIcon({
                iconSize: [16, 16],
                html: '<div class="arrow" style="-ms-transform: rotate(' + direction + 'deg);-webkit-transform: rotate(' + direction + 'deg);-moz-transform: rotate(' + direction + 'deg);-o-transform: rotate(' + direction + 'deg);transform: rotate(' + direction + 'deg)"></div>',
                className: 'just-arrow'
            })
        }).on('mouseover', function () {
            this.openPopup();
        });
    }

    var timeMarkerOptions = {
        radius: 3,
        fillColor: '#000',
        fillOpacity: 1,
        weight: 0,
    };

    function closeMap() {
        mapContainer.style.display = 'none';
        return false;
    }

    window.onkeydown = function(event) {
        if (map && event.keyCode === 27) {
            closeMap();
        }
    };

    var closeButton = L.control();

    closeButton.onAdd = function() {
        var div = document.createElement('div');
        div.className = 'leaflet-bar';
        var a = document.createElement('a');
        a.href = '#';
        a.style.width = 'auto';
        a.style.padding = '0 8px';
        a.setAttribute('role', 'button');
        a.innerHTML = 'Close map';
        a.onclick = closeMap;
        div.appendChild(a);
        return div;
    };

    function openMap(event) {
        var row = event.target.parentElement.parentElement,
            previous = row.previousElementSibling,
            next = row.nextElementSibling,
            details = document.getElementById('details'),
            dateTime,
            popup,
            delta,
            coordinates,
            line = [],
            bounds,
            latDistance,
            lngDistance,
            timeDistance,
            previousTime,
            previousCoordinates;

        mapContainer.style.display = 'block';

        var routeOrVehicle = row.children[0].innerHTML,
            journey = row.children[1].innerHTML,
            destination = row.children[2].innerHTML;

        if (destination) {
            destination = ' to ' + destination;
        }
        details.innerHTML = '<p>' + routeOrVehicle + ' – ' + journey + destination + '</p>';

        if (previous && previous.children[3].children[0]) {
            var previousButton = document.createElement('a');
            previousButton.href = '#';
            previousButton.innerHTML = '← ' + previous.children[1].innerHTML;
            previousButton.onclick = function() {
                previous.children[3].children[0].click();
                return false;
            };
            var previousP = document.createElement('p');
            previousP.className = 'previous';
            previousP.appendChild(previousButton);
            details.appendChild(previousP);
        }
        if (next && next.children[3].children[0]) {
            var nextButton = document.createElement('a');
            nextButton.href = '#';
            nextButton.innerHTML = next.children[1].innerHTML + ' →';
            nextButton.onclick = function() {
                next.children[3].children[0].click();
                return false;
            };
            var nextP = document.createElement('p');
            nextP.className = 'next';
            nextP.appendChild(nextButton);
            details.appendChild(nextP);
        }

        reqwest('/journeys/' + event.target.getAttribute('data-journey-id') + '.json', function(locations) {

            if (map) {
                layerGroup.clearLayers();
                map.invalidateSize();
            } else {
                map =  L.map('map');
                layerGroup.addTo(map);

                map.attributionControl.setPrefix('');

                L.tileLayer(tileURL, {
                    attribution: '<a href="https://www.maptiler.com/copyright/">© MapTiler</a> <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>'
                }).addTo(map);

                closeButton.addTo(map);
            }

            var j,
                minutes;

            for (var i = locations.length - 1; i >= 0; i -= 1) {
                dateTime = new Date(locations[i].datetime);
                popup = dateTime.toTimeString().slice(0, 8);
                delta = locations[i].delta;
                if (delta) {
                    popup += '<br>About ';
                    if (delta > 0) {
                        popup += delta;
                    } else {
                        popup += delta * -1;
                    }
                    popup += ' minute';
                    if (delta !== 1 && delta !== -1) {
                        popup += 's';
                    }
                    if (delta > 0) {
                        popup += ' early';
                    } else {
                        popup += ' late';
                    }
                }
                coordinates = L.latLng(locations[i].coordinates[1], locations[i].coordinates[0]);
                getMarker(coordinates, locations[i].direction).bindPopup(popup).addTo(layerGroup);
                if (previousCoordinates) {

                    latDistance = previousCoordinates.lat - coordinates.lat;
                    lngDistance = previousCoordinates.lng - coordinates.lng;
                    timeDistance = previousTime.getTime() - dateTime.getTime();

                    minutes = timeDistance / 60000;
                    for (j = minutes; j > 0; j -= 1) {
                        L.circleMarker(
                            L.latLng(
                                previousCoordinates.lat - latDistance/minutes,
                                previousCoordinates.lng - lngDistance/minutes),
                            timeMarkerOptions
                        ).addTo(layerGroup);
                    }
                }
                line.push(coordinates);
                previousTime = dateTime;
                previousCoordinates = coordinates;
            }
            line = L.polyline(line, {
                style: {
                    weight: 3,
                    color: '#87f'
                }
            });
            line.addTo(layerGroup);
            bounds = line.getBounds();
            map.fitBounds(bounds);
            map.setMaxBounds(bounds.pad(.5));
            line.bringToBack();
        });
    }

    var i,
        buttons = document.getElementsByTagName('button');

    for (i = buttons.length - 1; i >= 0; i -= 1) {
        buttons[i].onclick = openMap;
    }
})();
