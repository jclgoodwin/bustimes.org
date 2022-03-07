/*jslint browser: true*/
/*global accessibleAutocomplete*/

(function () {
    'use strict';

    document.getElementById('id_other_vehicle_type').parentNode.remove();

    // vehicle type
    accessibleAutocomplete.enhanceSelectElement({
        selectElement: document.getElementById('id_vehicle_type'),
        name: 'other_vehicle_type',
    });

    // other colour
    function toggleOtherColour() {
        var otherCheckbox = document.querySelector('#id_colours [value="Other"]');
        if (otherCheckbox) {
            var display = otherCheckbox.checked ? '' : 'none';
            document.getElementById('id_other_colour').parentNode.style.display = display;
        }
    }
    var radios = document.querySelectorAll('#id_colours [type="radio"]');
    for (var i = radios.length - 1; i >= 0; i -= 1) {
        radios[i].addEventListener('change', toggleOtherColour);
    }
    toggleOtherColour();
})();
