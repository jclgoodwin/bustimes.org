(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest, Cowboy
    */

    var map = L.map('hugemap'),
        tileURL = 'https://maps.bustimes.org/styles/klokantech-basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png',
        statusBar = L.control({
            position: 'topright'
        }),
        lastReq,
        timeout,
        oldVehicles = {},
        newVehicles = {};

    map.attributionControl.setPrefix('');

    L.tileLayer(tileURL, {
        attribution: '<a href="https://www.maptiler.com/copyright/">© MapTiler</a> <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>'
    }).addTo(map);

    statusBar.onAdd = function () {
        var div = L.DomUtil.create('div', 'hugemap-status');
        return div;
    };
    statusBar.addTo(map);

    function getRotation(direction) {
        if (direction === null) {
            return '';
        }
        var rotation = 'transform: rotate(' + direction + 'deg)';
        return '-ms-' + rotation + ';-webkit-' + rotation + ';-moz-' + rotation + ';-o-' + rotation + ';' + rotation;
    }

    function getIcon(service, direction, livery, textColour) {
        if (direction === null) {
            var html = '';
        } else {
            html = '<div class="arrow" style="' + getRotation(direction) + '"></div>';
        }
        var className = 'bus';
        if (livery) {
            var style = 'background:' + livery;
            className += ' coloured';
            if (textColour) {
                className += ' white-text';
            }
            style += ';';
        } else {
            style = '';
        }
        if (direction < 180) {
            direction -= 90;
        } else {
            direction -= 270;
        }
        style += getRotation(direction);
        html += '<div class="' + className + '" style="' + style + '">';
        if (service) {
            html += service.line_name;
        }
        html += '</div>';
        return L.divIcon({
            iconSize: [20, 20],
            html: html,
            popupAnchor: [0, -5],
        });
    }

    function handleVehicle(data) {
        if (data.properties.vehicle.url in oldVehicles) {
            var marker = oldVehicles[data.properties.vehicle.url];
            newVehicles[data.properties.vehicle.url] = marker;
            if (marker.datetime === data.properties.datetime) {
                return;
            }
        }

        var icon = getIcon(data.properties.service, data.properties.direction, data.properties.vehicle.livery, data.properties.vehicle.text_colour),
            latLng = L.latLng(data.geometry.coordinates[1], data.geometry.coordinates[0]);

        if (marker) {
            marker.setLatLng(latLng);
            marker.setIcon(icon);
        } else {
            marker = L.marker(latLng, {
                icon: icon
            });
            marker.addTo(map);
            newVehicles[data.properties.vehicle.url] = marker;
        }
        marker.datetime = data.properties.datetime;

        var popup = '';
        if (data.properties.service) {
            if (data.properties.service.url) {
                popup = '<a href="' + data.properties.service.url + '">' + data.properties.service.line_name + '</a>';
            } else {
                popup = data.properties.service.line_name;
            }
        }
        if (data.properties.destination) {
            popup += ' to ' + data.properties.destination;
        }

        if (data.properties.operator) {
            if (popup) {
                popup += '<br>';
            }
            popup += data.properties.operator + '<br>';
        }

        if (data.properties.vehicle) {
            popup += '<a href="' + data.properties.vehicle.url + '">' + data.properties.vehicle.name + '</a>';
            if (data.properties.vehicle.type) {
                popup += ' - ' + data.properties.vehicle.type;
            }
            if (data.properties.vehicle.notes) {
                popup += ' - ' + data.properties.vehicle.notes;
            }
            popup += '<br>';
        }

        if (data.properties.delta === 0) {
            popup += 'On time<br>';
        } else if (data.properties.delta) {
            popup += 'About ';
            if (data.properties.delta > 0) {
                popup += data.properties.delta;
            } else {
                popup += data.properties.delta * -1;
            }
            popup += ' minute';
            if (data.properties.delta !== 1 && data.properties.delta !== -1) {
                popup += 's';
            }
            if (data.properties.delta > 0) {
                popup += ' early';
            } else {
                popup += ' late';
            }
            popup += '<br>';
        }

        var dateTime = new Date(data.properties.datetime);
        popup += 'Updated at ' + dateTime.toTimeString().slice(0, 5);

        if (data.properties.source === 75 && data.properties.service && data.properties.service.url) {
            popup += '<br>(Updates if someone views<br><a href="' + data.properties.service.url + '">the ' + data.properties.service.line_name + ' page</a>)';
        }

        marker.bindPopup(popup);
    }


    function processData(data) {
        for (var i = data.features.length - 1; i >= 0; i -= 1) {
            handleVehicle(data.features[i]);
        }
        for (var vehicle in oldVehicles) {
            if (!(vehicle in newVehicles)) {
                map.removeLayer(oldVehicles[vehicle]);
            }
        }
        oldVehicles = newVehicles;
        newVehicles = {};
        statusBar.getContainer().innerHTML = '';
    }

    function load(map, statusBar) {
        statusBar.getContainer().innerHTML = 'Loading\u2026';
        if (lastReq) {
            lastReq.abort();
        }
        var bounds = map.getBounds();
        lastReq = reqwest(
            '/vehicles.json?ymax=' + bounds.getNorth() + '&xmax=' + bounds.getEast() + '&ymin=' + bounds.getSouth() + '&xmin=' + bounds.getWest(),
            function(data) {
                if (data) {
                    processData(data);
                }
                timeout = setTimeout(function() {
                    load(map, statusBar);
                }, 10000);
            }
        );
    }

    function handleMoveEnd(event) {
        clearTimeout(timeout);
        load(map, statusBar);

        var latLng = event.target.getCenter(),
            string = event.target.getZoom() + '/' + Math.round(latLng.lat * 10000) / 10000 + '/' + Math.round(latLng.lng * 10000) / 10000;

        if (history.replaceState) {
            history.replaceState(null, null, location.pathname + '#' + string);
        }
        if (window.localStorage) {
            localStorage.setItem('vehicleMap', string);
        }

        var links = document.getElementsByTagName('header')[0].getElementsByTagName('a');
        for (var i = links.length - 1; i >= 0; i -= 1) {
            if (links[i].href.indexOf('/map') !== -1) {
                links[i].href = '/map#' + string;
                break;
            }
        }
    }

    map.on('moveend', Cowboy.debounce(500, handleMoveEnd));

    window.onhashchange = function(event) {
        var parts = event.target.location.hash.substr(1).split('/');
        if (parts.length == 3) {
            map.setView([parts[1], parts[2]], parts[0]);
        }
    };

    var parts;
    if (location.hash) {
        parts = location.hash.substring(1).split('/');
    } else if (localStorage.vehicleMap) {
        parts = localStorage.vehicleMap.split('/');
    }
    if (parts) {
        map.setView([parts[1], parts[2]], parts[0]);
    } else {
        map.setView([51.9, 0.9], 9);
    }

    function handleVisibilityChange(event) {
        if (event.target.hidden) {
            clearTimeout(timeout);
        } else {
            load(map, statusBar);
        }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange);

    load(map, statusBar);
})();
