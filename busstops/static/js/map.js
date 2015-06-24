(function (locations, bounds, center) {
    if (locations.length && document.getElementById('map').clientWidth === 460) {
        var map = L.map('map');
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);

        for (var i = 0; i < locations.length; i++) {
            L.marker([locations[i][0], locations[i][1]]).addTo(map).bindPopup(locations[i][2]).openPopup();
        }

        if (bounds && center) {
            map.fitBounds(bounds).setView(center);
        } else {
            map.setView([locations[0][0], locations[0][1]], 17);
        }
    }
})(mapOptions.locations, mapOptions.bounds || false, mapOptions.center || false);
