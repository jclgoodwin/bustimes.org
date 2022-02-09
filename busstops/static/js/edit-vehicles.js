/*jslint browser: true*/

(function() {
    'use strict';

    // checkbox ranges of rows
    var lastInput,
        table = document.querySelector('table'),
        checkboxes = table.querySelectorAll('input');

    function handleBoxCheck(event) {
        if (event.shiftKey && lastInput) {
            var from = event.target.parentNode.parentNode.rowIndex,
                to = lastInput.parentNode.parentNode.rowIndex,
                min = Math.min(from, to),
                max = Math.max(from, to);
            for (var i = min + 1; i < max; i += 1) {
                var row = table.rows[i];
                var checkbox = row.querySelector('input');
                if (checkbox) {
                    checkbox.checked = lastInput.checked;
                    checkbox.parentNode.parentNode.style.background = checkbox.checked ? '#ef9' : '';
                }
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
})();
