(function () {

    var map = L.map('hugemap', {
        minZoom: 5,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors',
        // subdomains: '1234',
    }).addTo(map);
    
    var statu = L.control({position: 'topright'});
    
    statu.onAdd = function (map) {
        var div = L.DomUtil.create('div', 'hugemap-status');
        return div;
    };
    
    statu.addTo(map);
    
    var points = L.layerGroup().addTo(map);
    
    map.on('moveend', function(e) {
        var zoom = e.target.getZoom(),
            bounds = e.target.getBounds();
        window.location.hash = e.target.getCenter().lat + ',' + e.target.getCenter().lng;
        if (zoom > 13) {
            statu.getContainer().innerHTML = 'Loading...';
            $.get('/stops.json', {
                ymax: bounds.getNorth(),
                xmax: bounds.getEast(),
                ymin: bounds.getSouth(),
                xmin: bounds.getWest(),
            }, function(data) {
                var layer = L.geoJson(data, {
                    pointToLayer: function(data, latlng) {
                        return L.marker(latlng).bindPopup('<a href="' + data.properties.url + '">' + data.properties.name + '</a>');
                    }
                }).addTo(map);
                points.clearLayers();
                layer.addTo(points);
                statu.getContainer().innerHTML = '';
            }, 'json');
        } else {
            points.clearLayers();
            statu.getContainer().innerHTML = 'Please zoom in to see stops';
        }
    });
    
    if (window.location.hash) {
        map.setView(window.location.hash.substr(1).split(','), 15);
    } else {
        map.setView([53.833333, -2.416667], 5);
        map.se
        map.on('locationError', function(e) {
            // window.alert('!');
            console.log(this);
        });
        map.locate({setView: true, maxZoom: 15});
    }

})();
