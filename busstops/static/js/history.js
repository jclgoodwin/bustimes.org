(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest
    */

    function getMarker(latlng, direction) {
        direction = direction || 0;
        return L.marker(latlng, {
            icon: L.divIcon({
                iconSize: [16, 8],
                html: '<div class="arrow" style="-ms-transform: rotate(' + direction + 'deg);-webkit-transform: rotate(' + direction + 'deg);-moz-transform: rotate(' + direction + 'deg);-o-transform: rotate(' + direction + 'deg);transform: rotate(' + direction + 'deg)"></div>',
                className: 'just-arrow'
            })
        });
    }


    function openMap(event) {
        var mapContainer = document.createElement('div');
        mapContainer.id = 'map';
        mapContainer.className = 'full-screen';
        var main = document.getElementsByTagName('main')[0];
        main.appendChild(mapContainer);

        var map =  L.map('map'),
            tileURL = 'https://maps.bustimes.org/styles/klokantech-basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png';

        map.attributionControl.setPrefix('');

        L.tileLayer(tileURL, {
            attribution: '<a href="https://www.maptiler.com/copyright/">© MapTiler</a> <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>'
        }).addTo(map);

        var closeButton = L.control();

        closeButton.onAdd = function(map) {
            var div = document.createElement('div');
            div.className = 'leaflet-bar';
            var a = document.createElement('a');
            a.href = '#';
            a.role = 'button';
            a.title = 'Close map';
            a.onclick = function() {
                map.remove();
                main.removeChild(mapContainer);
            };
            a.innerHTML = '❌';
            div.appendChild(a);
            return div;
        };

        closeButton.onRemove = function() {
        };

        closeButton.addTo(map);

        reqwest('/journeys/' + event.target.getAttribute('data-journey-id') + '.json', function(locations) {
            var i,
                dateTime,
                popup,
                delta,
                coordinates,
                line = [],
                bounds;

            for (i = locations.length - 1; i >= 0; i -= 1) {
                dateTime = new Date(locations[i].datetime);
                popup = dateTime.toTimeString().slice(0, 5);
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
                coordinates = [locations[i].coordinates[1], locations[i].coordinates[0]];
                getMarker(coordinates, locations[i].direction).bindPopup(popup).addTo(map);
                line.push(coordinates);
            }
            line = L.polyline(line);
            line.addTo(map);
            bounds = line.getBounds();
            map.fitBounds(bounds);
            map.setMaxBounds(bounds.pad(.5));
        });
    }

    var i,
        buttons = document.getElementsByTagName('button');

    for (i = buttons.length - 1; i >= 0; i -= 1) {
        buttons[i].onclick = openMap;
    }
})();
