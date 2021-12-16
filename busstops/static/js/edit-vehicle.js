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
    var spareMachineElement = document.getElementById('id_spare_ticket_machine');
    function handleWithdrawn() {
        var display = (withdrawnElement.checked || spareMachineElement.checked) ? 'none' : '';
        var elements = document.querySelectorAll('.edit-vehicle > *, .edit-vehicles > *');

        for (var i = elements.length - 1; i >= 0; i -= 1) {
            var element = elements[i];
            if (!element.querySelector('input, label') || element.querySelector('#id_withdrawn, #id_spare_ticket_machine')) {
                // don't show/hide non-form field paragraph or check box
                continue;
            }
            if (withdrawnElement.checked && element.querySelector('#id_url') && !spareMachineElement.checked) {
                // try to keep the url field shown for 'withdrawn' but not for 'spare ticket machine'
                // it's not working perfectly (the url field will sometimes get stuck hidden) but fuck it
                continue;
            }
            element.style.display = display;

        }
        if (display === '') {
            toggleOtherColour();
        }
    }
    if (withdrawnElement) {
        withdrawnElement.addEventListener('change', handleWithdrawn);
        spareMachineElement.addEventListener('change', handleWithdrawn);
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
