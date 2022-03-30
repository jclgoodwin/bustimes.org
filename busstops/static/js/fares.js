'use strict';

/*jslint
    browser: true
*/
/*global
    reqwest
*/

(function () {

    var fareTables = document.getElementById('fare-tables');
    if (fareTables) {
        fareTables.onchange = function(event) {
            if (event.target.value) {
                var container = document.getElementById('fare-table');
                container.className = 'loading';
                reqwest('/fares/tables/' + event.target.value, function(data) {
                    container.innerHTML = data;
                    container.className = '';
                });
            }
        };
    }

})();
