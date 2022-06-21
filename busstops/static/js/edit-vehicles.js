/*jslint browser: true*/

(function() {
    'use strict';

    // checkbox ranges of rows
    var lastInput,
        table = document.querySelector('table');

    if (table) {
        return;
    }

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
                    checkbox.parentNode.parentNode.className = checkbox.checked ? 'is-highlighted' : '';
                }
            }
        }
        lastInput = event.target;
        lastInput.parentNode.parentNode.className = lastInput.checked ? 'is-highlighted' : '';
    }

    var checkboxes = table.querySelectorAll('input');

    for (var i = checkboxes.length - 1; i >= 0; i -= 1) {
        var checkbox = checkboxes[i];
        checkbox.addEventListener('click', handleBoxCheck);
        if (checkbox.checked) {
            checkbox.parentNode.parentNode.className = 'is-highlighted';
        }
    }
})();
