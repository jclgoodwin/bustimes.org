(function () {

    if (document.getElementById('map').clientWidth > 0) {

        var items = document.getElementsByTagName('li'),
            i,
            metaElements,
            locations = [],
            labels = [];

        for (i = 0; i < items.length; i++) {
            if (items[i].getAttribute('itemtype') === 'https://schema.org/BusStop') {
                metaElements = items[i].getElementsByTagName('meta');
                locations.push([
                    parseFloat(metaElements[0].getAttribute('content')),
                    parseFloat(metaElements[1].getAttribute('content'))
                    ]);
                labels.push(items[i].innerHTML);
            }
        }

        if (! locations.length) {
            metaElements = document.getElementsByTagName('meta');
            for (i = 0; i < metaElements.length; i++) {
                if (metaElements[i].getAttribute('itemprop') === 'latitude') {
                    locations.push([
                        parseFloat(metaElements[i].getAttribute('content')),
                        parseFloat(metaElements[i+1].getAttribute('content'))
                        ]);
                }
            }
        }

        if (locations.length) {
            var map = L.map('map');
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
            }).addTo(map);

            if (locations.length === 1) {
                L.circleMarker(locations[0]).addTo(map);
                map.setView(locations[0], 17);
            } else {
                for (i = 0; i < locations.length; i++) {
                    L.circleMarker(locations[i]).addTo(map).bindPopup(labels[i]);
                }
                var polyline = L.polyline(locations);
                map.fitBounds(polyline.getBounds());
            }
        }

    }

})();
