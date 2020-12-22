/*jslint browser: true*/
/*global accessibleAutocomplete*/

(function() {
    'use strict';

    // vehicle
    accessibleAutocomplete.enhanceSelectElement({
        selectElement: document.getElementById('id_vehicle_type')
    });

    // checkbox ranges of rows
    var lastInput,
        checkboxes = document.querySelectorAll('.fleet input');

    function handleBoxCheck(event) {
        if (event.shiftKey && lastInput) {
            var from = event.target.parentNode.parentNode.rowIndex - 1,
                to = lastInput.parentNode.parentNode.rowIndex - 1,
                min = Math.min(from, to),
                max = Math.max(from, to);
            for (var i = min + 1; i < max; i += 1) {
                var checkbox = checkboxes[i];
                checkbox.checked = lastInput.checked;
                checkbox.parentNode.parentNode.style.background = checkbox.checked ? '#ef9' : '';
            }
        }
        lastInput = event.target;
        lastInput.parentNode.parentNode.style.background = lastInput.checked ? '#ef9' : '';
    }

    for (var i = checkboxes.length - 1; i >= 0; i -= 1) {
        var checkbox = checkboxes[i];
        checkbox.addEventListener('click', handleBoxCheck);
        if (checkbox.checked) {
            checkbox.parentNode.parentNode.style.background = '#ef9';
        }
    }

    // other colour
    function toggleOtherColour() {
        var otherCheckbox = document.querySelector('#id_colours [value="Other"]');
        var display = otherCheckbox.checked ? '' : 'none';
        document.getElementById('id_other_colour').parentNode.style.display = display;
    }
    var radios = document.querySelectorAll('#id_colours [type="radio"]');
    for (i = radios.length - 1; i >= 0; i -= 1) {
        radios[i].addEventListener('change', toggleOtherColour);
    }
    toggleOtherColour();
})();
