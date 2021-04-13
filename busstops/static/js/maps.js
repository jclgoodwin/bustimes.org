(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L
    */

    var tiles = 'https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png';
    var attribution = '<a href="https://stadiamaps.com/">© Stadia Maps</a> <a href="https://openmaptiles.org/">© OpenMapTiles</a> <a href="https://www.openstreetmap.org/about/">© OpenStreetMap contributors</a>';

    function getTransform(heading, scale) {
        if (heading === null && !scale) {
            return '';
        }
        var transform = 'transform:';
        if (heading !== null) {
            transform += ' rotate(' + heading + 'deg)';
        }
        if (scale) {
            transform += ' scale(1.5)';
        }
        return '-webkit-' + transform + ';' + transform + ';';
    }

    function getBusIcon(item, active) {
        var className = 'bus';
        if (active) {
            className += ' selected';
        }
        var heading = item.heading;
        if (heading !== null) {
            var arrow = '<div class="arrow" style="' + getTransform(heading, active) + '"></div>';
            if (heading < 180) {
                className += ' right';
                heading -= 90;
            } else {
                heading -= 270;
            }
        }
        var style = getTransform(heading, active);
        if (item.vehicle.livery) {
            className += ' livery-' + item.vehicle.livery;
        } else if (item.vehicle.css) {
            style += 'background:' + item.vehicle.css;
            if (item.vehicle.text_colour) {
                className += ' white-text';
            }
        }
        var html = '<div class="' + className + '" style="' + style + '">';
        if (item.service) {
            html += item.service.line_name;
        }
        html += '</div>';
        if (arrow) {
            html += arrow;
        }
        return L.divIcon({
            iconSize: [20, 20],
            html: html,
            popupAnchor: [0, -5],
        });
    }

    var agoTimeout;

    function getPopupContent(item) {
        var now = new Date();
        var then = new Date(item.datetime);
        var ago = Math.round((now.getTime() - then.getTime()) / 1000);

        if (item.service) {
            var content = item.service.line_name;
            if (item.destination) {
                content += ' to ' + item.destination;
            }
            if (item.service.url) {
                content = '<a href="' + item.service.url + '">' + content + '</a>';
            }
        } else {
            content = '';
        }

        content += '<a href="' + item.vehicle.url + '">' + item.vehicle.name + '</a>';

        if (item.vehicle.features) {
            content += item.vehicle.features + '<br>';
        }
        if (item.seats) {
            content += '<img src="/static/svg/seat.svg" width="14" height="14" alt="seats"> ' + item.seats + '<br>';
        }
        if (item.wheelchair) {
            content += '<img src="/static/svg/wheelchair.svg" width="14" height="14" alt="wheelchair space"> ' + item.wheelchair + '<br>';
        }

        if (ago >= 1800) {
            content += 'Updated at ' + then.toTimeString().slice(0, 8);
        } else {
            content += '<time datetime="' + item.datetime + '" title="' + then.toTimeString().slice(0, 8) + '">';
            if (ago >= 59) {
                var minutes = Math.round(ago / 60);
                if (minutes === 1) {
                    content += '1 minute';
                } else {
                    content += minutes + ' minutes';
                }
                agoTimeout = setTimeout(updatePopupContent, (61 - ago % 60) * 1000);
            } else {
                if (ago === 1) {
                    content += '1 second';
                } else {
                    content += ago + ' seconds';
                }
                agoTimeout = setTimeout(updatePopupContent, 1000);
            }
            content += ' ago</time>';
        }
        return content;
    }

    function updatePopupContent() {
        if (agoTimeout) {
            clearTimeout(agoTimeout);
        }
        var marker = window.bustimes.vehicleMarkers[window.bustimes.clickedMarker];
        if (marker) {
            var item = marker.options.item;
            marker.getPopup().setContent(getPopupContent(item));
        }
    }


    function handlePopupOpen(event) {
        var marker = event.target;
        var item = marker.options.item;

        window.bustimes.clickedMarker = item.id;
        updatePopupContent();

        marker.setIcon(getBusIcon(item, true));
        marker.setZIndexOffset(2000);
    }

    function handlePopupClose(event) {
        if (window.bustimes.map.hasLayer(event.target)) {
            window.bustimes.clickedMarker = null;
            // make the icon small again
            event.target.setIcon(getBusIcon(event.target.options.item));
            event.target.setZIndexOffset(1000);
        }
    }

    function handleVehicle(item) {
        var isClickedMarker = item.id === window.bustimes.clickedMarker,
            icon = getBusIcon(item, isClickedMarker),
            latLng = L.latLng(item.coordinates[1], item.coordinates[0]);

        if (item.id in window.bustimes.vehicleMarkers) {
            // update existing
            var marker = window.bustimes.vehicleMarkers[item.id];
            marker.setLatLng(latLng);
            marker.setIcon(icon);
            marker.options.item = item;
            if (isClickedMarker) {
                window.bustimes.vehicleMarkers[item.id] = marker;  // make updatePopupContent work
                updatePopupContent();
            }
        } else {
            marker = L.marker(latLng, {
                icon: getBusIcon(item, isClickedMarker),
                zIndexOffset: 1000,
                item: item
            });
            marker.addTo(window.bustimes.map)
                .bindPopup('', {
                    autoPan: false
                })
                .on('popupopen', handlePopupOpen)
                .on('popupclose', handlePopupClose);
        }
        return marker;
    }

    function handleVehicles(items) {
        var newMarkers = {};
        for (var i = items.length - 1; i >= 0; i--) {
            var item = items[i];
            newMarkers[item.id] = handleVehicle(item);
        }
        // remove old markers
        for (i in window.bustimes.vehicleMarkers) {
            if (!(i in newMarkers)) {
                window.bustimes.map.removeLayer(window.bustimes.vehicleMarkers[i]);
            }
        }
        window.bustimes.vehicleMarkers = newMarkers;
    }

    window.bustimes = {
        doTileLayer: function(map) {
            map.attributionControl.setPrefix('');
            L.tileLayer(tiles, {
                attribution: attribution
            }).addTo(map);
        },

        getPopupContent: getPopupContent,

        updatePopupContent: updatePopupContent,

        getBusIcon: getBusIcon,

        getTransform: getTransform,

        handleVehicles: handleVehicles,

        vehicleMarkers: {},
    };
})();
