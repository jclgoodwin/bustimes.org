(function (locations) {
    if (locations.length && document.getElementById('map').clientWidth === 460) {
        var map = L.map('map');
        L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);
        console.log(locations);
        for (var i = 0; i < locations.length; i++) {
            L.marker([locations[i][0], locations[i][1]]).addTo(map).bindPopup(locations[i][2]).openPopup();
        }
        // if (locations.length === 1) {
            map.setView([locations[0][0], locations[0][1]], 17);
        // } else {
            
        // }
    }
})(mapLocations);
