(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest, d3
    */

    var map,
        mapContainer = document.getElementById('journey-overlay'),
        layerGroup = L.layerGroup(),
        tileURL = 'https://maps.bustimes.org/styles/klokantech-basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png';

    function getMarker(latlng, direction) {
        direction = (direction || 0) - 135;
        return L.marker(latlng, {
            icon: L.divIcon({
                iconSize: [20, 20],
                html: '<div class="arrow" style="-ms-transform: rotate(' + direction + 'deg);-webkit-transform: rotate(' + direction + 'deg);-moz-transform: rotate(' + direction + 'deg);-o-transform: rotate(' + direction + 'deg);transform: rotate(' + direction + 'deg)"></div>',
                className: 'just-arrow'
            })
        });
    }

    function doGraph(locations) {
        var svg = d3.select('#details').append('svg').attr('width', 400).attr('height', 150);

        // var minSpeed = 0;
        var maxSpeed = 0;

        var data = locations.map(function(location) {
            // if (location.speed < minSpeed) {
            //     minSpeed = location.speed;
            // }
            if (location.speed > maxSpeed) {
                maxSpeed = location.speed;
            }
            return {
                datetime: new Date(location.datetime),
                speed: location.speed
            };
        });

        var timeScale = d3.scaleTime().domain([
            data[0].datetime,
            data[data.length-1].datetime
        ]).range([0, 380]);
        var timeAxis = d3.axisBottom(timeScale);
        svg.append('g').attr('transform', 'translate(20,130)').call(timeAxis.tickFormat(d3.timeFormat('%H:%M')));

        var speedScale = d3.scaleLinear().domain([
            maxSpeed,
            0
        ]).range([0, 130]);
        var speedAxis = d3.axisLeft(speedScale);
        svg.append('g').attr('transform', 'translate(20,0)').call(speedAxis);


        var line = d3.line().x(function(d) {
            return timeScale(d.datetime);
        }).y(function(d) {
            return speedScale(d.speed);
        });

        svg.append('path').attr('transform', 'translate(20,0)').attr('fill', 'none').attr('stroke', '#000').datum(data).attr('d', line);
    }

    function closeMap() {
        mapContainer.style.display = 'none';
        return false;
    }

    window.onkeydown = function(event) {
        if (map && event.keyCode === 27) {
            closeMap();
        }
    };

    function openMap(event) {
        var row = event.target.parentElement.parentElement,
            previous = row.previousElementSibling,
            next = row.nextElementSibling;

        reqwest('/journeys/' + event.target.getAttribute('data-journey-id') + '.json', function(locations) {
            var i,
                details = document.getElementById('details'),
                dateTime,
                popup,
                delta,
                coordinates,
                line = [],
                bounds;

            mapContainer.style.display = 'block';

            details.innerHTML = '<p>' + row.children[0].innerHTML + ' – ' + row.children[1].innerHTML + ' to ' + row.children[2].innerHTML + '</p>';

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

                closeButton.addTo(map);
            }

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
                getMarker(coordinates, locations[i].direction).bindPopup(popup).addTo(layerGroup);
                line.push(coordinates);
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

            doGraph(locations);

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
        });
    }

    var i,
        buttons = document.getElementsByTagName('button');

    for (i = buttons.length - 1; i >= 0; i -= 1) {
        buttons[i].onclick = openMap;
    }
})();
