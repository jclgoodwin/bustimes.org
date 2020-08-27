/*jslint browser: true*/
/*global accessibleAutocomplete*/

window.addEventListener('load', function() {
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
            checkboxes.forEach(function(checkbox, i) {
                if (i > min && i < max) {
                    checkbox.checked = lastInput.checked;
                    checkbox.parentNode.parentNode.style.background = checkbox.checked ? '#ef9' : '';
                }
            });
        }
        lastInput = event.target;
        lastInput.parentNode.parentNode.style.background = lastInput.checked ? '#ef9' : '';
    }

    checkboxes.forEach(function(checkbox) {
        checkbox.addEventListener('click', handleBoxCheck);
        if (checkbox.checked) {
            checkbox.parentNode.parentNode.style.background = '#ef9';
        }
    });

    // other colour
    function toggleOtherColour() {
        var otherCheckbox = document.querySelector('#id_colours [value="Other"]');
        var display = otherCheckbox.checked ? '' : 'none';
        document.getElementById('id_other_colour').parentNode.style.display = display;
    }
    document.querySelectorAll('#id_colours [type="radio"]').forEach(function(radio) {
        radio.addEventListener('change', toggleOtherColour);
    });
    toggleOtherColour();
});
