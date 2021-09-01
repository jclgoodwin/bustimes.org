/*jslint browser: true*/
/*global accessibleAutocomplete*/

(function () {
    'use strict';

    // vehicle type
    accessibleAutocomplete.enhanceSelectElement({
        selectElement: document.getElementById('id_vehicle_type')
    });

    // withdrawn
    var withdrawnElement = document.getElementById('id_withdrawn');
    function handleWithdrawn() {
        var display = withdrawnElement.checked ? 'none' : '';
        var elements = document.querySelectorAll('.edit-vehicle > *, .edit-vehicles > *');

        for (var i = elements.length - 1; i >= 0; i -= 1) {
            var element = elements[i];
            if ((element.querySelector('input, label')) && !element.querySelector('#id_withdrawn, #id_url, #id_user')) {
                element.style.display = display;
            }
        }
        if (display === '') {
            toggleOtherColour();
        }
    }
    if (withdrawnElement) {
        withdrawnElement.addEventListener('change', handleWithdrawn);
        handleWithdrawn();
    }

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
