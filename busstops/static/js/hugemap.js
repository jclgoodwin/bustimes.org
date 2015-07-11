(function () {

    var map = L.map('hugemap', {
        minZoom: 5,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    
    var pin = L.icon({
        iconUrl:    '/static/pin.svg',
        iconSize:   [16, 22],
        iconAnchor: [8, 22],
        popupAnchor: [0, -22],
    });

    var statusBar = L.control({position: 'topright'});
    
    statusBar.onAdd = function (map) {
        var div = L.DomUtil.create('div', 'hugemap-status');
        return div;
    };
    
    statusBar.addTo(map);
    
    var points = L.layerGroup().addTo(map);
    var zoom;

    function loadStops(map, statusBar) {
        var bounds = map.getBounds(),
            hw = map.highwater;
        if (!hw || !hw.contains(bounds)) {
            statusBar.getContainer().innerHTML = 'Loading...';
            $.get('/stops.json', {
                ymax: bounds.getNorth(),
                xmax: bounds.getEast(),
                ymin: bounds.getSouth(),
                xmin: bounds.getWest(),
            }, function(data) {
                var layer = L.geoJson(data, {
                    pointToLayer: function(data, latlng) {
                        return L.marker(latlng, {
                            icon: pin
                        }).bindPopup('<a href="' + data.properties.url + '">' + data.properties.name + '</a>');
                    }
                }).addTo(map);
                points.clearLayers();
                layer.addTo(points);
                map.highwater = bounds;
                statusBar.getContainer().innerHTML = '';
            }, 'json');
        }
    }

    map.on('moveend', function(e) {
        window.location.hash = e.target.getCenter().lat + ',' + e.target.getCenter().lng;
        if (e.target.getZoom() > 13) {
            loadStops(this, statusBar);
        } else {
            statusBar.getContainer().innerHTML = 'Please zoom in to see stops';
            // points.clearLayers();
        }
    });
    
    if (window.location.hash) {
        map.setView(window.location.hash.substr(1).split(','), 15);
    } else {
        map.setView([53.833333, -2.416667], 5);
        map.locate({setView: true, maxZoom: 15});
    }

})();
