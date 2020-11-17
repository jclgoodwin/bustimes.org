(function () {
    'use strict';

    /*jslint
        browser: true
    */
    /*global
        L, reqwest, loadjs
    */

    var container = document.getElementById('map'),
        map = L.map(container),
        bounds;

    L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', {
        attribution: '<a href="https://stadiamaps.com/">© Stadia Maps</a> <a href="https://openmaptiles.org/">© OpenMapTiles</a> <a href="https://www.openstreetmap.org/about/">© OpenStreetMap contributors</a>',
    }).addTo(map);

    var services = L.geoJson(SERVICES, {
        style: {
            weight: 3,
            color: '#87f',
            interactive: true
        },
        onEachFeature: function(feature, layer) {
            layer.bindTooltip(feature.properties.name);
            layer.on('mouseover', function(event) {
                event.target.setStyle({
                    color: '#000',
                });
                event.target.bringToFront();
            }).on('mouseout', function(event) {
                event.target.setStyle({
                    color: '#87f'
                })
            });
        },
    })

    map.fitBounds(services.getBounds());

    services.addTo(map);
})();
 