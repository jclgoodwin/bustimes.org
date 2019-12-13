(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest, loadjs
    */

    var container = document.getElementById('map'),
        service = container.getAttribute('data-service'),
        map,
        statusBar,
        bounds,
        lastReq,
        response,
        oldVehicles = {},
        newVehicles = {},
        busesOnline = document.getElementById('buses-online'),
        button = busesOnline.getElementsByTagName('button')[0];

    function openMap() {
        container.className += ' expanded';
        if (document.body.style.paddingTop) {
            container.style.top = document.body.style.paddingTop;
        }
        document.body.style.overflow = 'hidden';

        if (map) {
            map.invalidateSize();
        } else {
            loadjs([window.LEAFLET_CSS_URL, window.LEAFLET_JS_URL], setUpMap);
            if (busesOnlineCount) {
                clearTimeout(timeout);
                load();
            }
        }
    }

    button.onclick = openMap;

    function setUpMap() {
        map = L.map(container),
        map.attributionControl.setPrefix('');
        L.tileLayer('https://maps.bustimes.org/styles/klokantech-basic/{z}/{x}/{y}' + (L.Browser.retina ? '@2x' : '') + '.png', {
            attribution: '<a href="https://www.maptiler.com/copyright/">© MapTiler</a> <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>'
        }).addTo(map);

        statusBar = L.control({
            position: 'bottomleft'
        });

        statusBar.onAdd = function() {
            var div = L.DomUtil.create('div', 'hugemap-status');
            return div;
        };

        statusBar.addTo(map);

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

        if (window.EXTENT) {
            map.fitBounds([[window.EXTENT[1], window.EXTENT[0]], [window.EXTENT[3], window.EXTENT[2]]]);
        }

        reqwest('/services/' + service + '.json', function(data) {
            L.geoJson(data.geometry, {
                style: {
                    weight: 3,
                    color: '#87f'
                }
            }).addTo(map);
            var options = {
                radius: 3,
                fillColor: '#fff',
                color: '#87f',
                weight: 2,
                fillOpacity: 1
            };

            L.geoJson(data.stops, {
                pointToLayer: function (feature, latlng) {
                    return L.circleMarker(latlng, options).bindPopup('<a href="' + feature.properties.url + '">' + feature.properties.name + '</a>');
                }
            }).addTo(map);
        });

        if (response) {
            processData(response);
        }
    }

    function getRotation(direction) {
        if (direction == null) {
            return '';
        }
        var rotation = 'transform: rotate(' + direction + 'deg)';
        return '-ms-' + rotation + ';-webkit-' + rotation + ';-moz-' + rotation + ';-o-' + rotation + ';' + rotation;
    }

    function getIcon(direction, livery, textColour) {
        if (direction !== null) {
            var arrow = '<div class="arrow" style="' + getRotation(direction) + '"></div>';
            if (direction < 180) {
                direction -= 90;
            } else {
                direction -= 270;
            }
        }
        var className = 'bus';
        if (livery) {
            var style = 'background:' + livery + ';';
            className += ' coloured';
            if (textColour) {
                className += ' white-text';
            }
        } else {
            style = '';
        }
        style += getRotation(direction);
        var html = '<div class="' + className + '" style="' + style + '"></div>';
        if (arrow) {
            html += arrow;
        }
        return L.divIcon({
            iconSize: [20, 20],
            html: html,
            popupAnchor: [0, -5],
        });
    }

    function handleVehicle(data) {
        var props = data.properties;

        if (props.vehicle.url in oldVehicles) {
            var marker = oldVehicles[props.vehicle.url];
            newVehicles[props.vehicle.url] = marker;
            if (marker.datetime === props.datetime) {
                return;
            }
        }

        var icon = getIcon(props.direction, props.vehicle.livery, props.vehicle.text_colour),
            latLng = L.latLng(data.geometry.coordinates[1], data.geometry.coordinates[0]);

        bounds.extend(latLng);

        if (marker) {
            marker.setLatLng(latLng);
            marker.setIcon(icon);
        } else {
            marker = L.marker(latLng, {
                icon: icon
            });
            marker.addTo(map);
            newVehicles[props.vehicle.url] = marker;
        }
        marker.datetime = props.datetime;


        if (props.destination) {
            var popup = props.destination;
            if (props.destination.indexOf(' to ') === -1) {
                popup = 'To ' + popup;
            }
        } else {
            popup = '';
        }


        popup += '<a href="' + props.vehicle.url + '">' + props.vehicle.name + '</a>';


        if (props.vehicle.decker) {
            var features = 'Double-decker';
            if (props.vehicle.coach) {
                features += ' coach';
            }
        } else if (props.vehicle.coach) {
            features = 'Coach';
        } else {
            features = '';
        }

        if (props.vehicle.features && props.vehicle.features.length) {
            if (features) {
                features += '<br>';
            }
            features += props.vehicle.features.join(', ');
        }

        if (features) {
            popup += features + '<br>';
        }


        if (props.delta === 0) {
            var delay = 'On time';
        } else if (props.delta) {
            delay = 'About ';
            if (props.delta > 0) {
                delay += props.delta;
            } else {
                delay += props.delta * -1;
            }
            delay += ' minute';
            if (props.delta !== 1 && props.delta !== -1) {
                delay += 's';
            }
            if (props.delta > 0) {
                delay += ' early';
            } else {
                delay += ' late';
            }
        }

        if (delay) {
            popup += delay + '<br>';
        }

        var dateTime = new Date(props.datetime);
        popup += 'Updated at ' + dateTime.toTimeString().slice(0, 5);

        marker.bindPopup(popup);
    }

    function processData(data) {
        bounds = L.latLngBounds();

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

        if (!map._loaded && bounds.isValid()) {
            map.fitBounds(bounds, {
                padding: [10, 10],
                maxZoom: 12
            });
        }
        statusBar.getContainer().innerHTML = '';
    }

    var timeout, busesOnlineCount;

    function load() {
        if (statusBar) {
            statusBar.getContainer().innerHTML = 'Loading\u2026';
        }
        if (lastReq) {
            lastReq.abort();
        }
        lastReq = reqwest('/vehicles.json?service=' + service, function(data) {
            if (lastReq.request.status === 200 && data && data.features) {
                if (!busesOnlineCount) { // first load
                    if (data.features.length) {
                        busesOnlineCount = document.createElement('span');
                        busesOnline.appendChild(busesOnlineCount);
                        if (document.addEventListener) {
                            document.addEventListener('visibilitychange', handleVisibilityChange);
                        }
                    } else {
                        if (statusBar) {
                            statusBar.getContainer().innerHTML = '';
                        }
                        return;
                    }
                }

                if (data.features.length === 0) {
                    busesOnlineCount.innerHTML = 'No buses online';
                } else if (data.features.length === 1) {
                    busesOnlineCount.innerHTML = '1 bus online';
                } else {
                    busesOnlineCount.innerHTML = data.features.length + ' buses online';
                }
                if (map) {
                    processData(data);
                } else {
                    response = data;
                }
            }
            timeout = setTimeout(function() {
                load();
            }, map ? 10000 : 120000); // 10 seconds or 2 minute
        });
    }

    function handleVisibilityChange(event) {
        if (event.target.hidden) {
            clearTimeout(timeout);
        } else {
            load();
        }
    }

    function closeMap() {
        container.className = container.className.replace(' expanded', '');
        document.body.style.overflow = '';
        window.location.hash = '';

        return false;
    }

    window.onkeydown = function(event) {
        if (event.keyCode === 27) {
            closeMap();
        }
    };

    window.onhashchange = function(event) {
        if (event.target.location.hash === '#map') {
            openMap();
        } else {
            closeMap();
        }
    };

    load();
    if (window.location.hash === '#map') {
        openMap();
    }

})();
