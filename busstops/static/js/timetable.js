'use strict';

/*jslint
    browser: true
*/
/*global
    ga
*/

(function() {
    var i,
        selects = document.getElementsByTagName('select'),
        options,
        ths;

    // correct date picker after using browser back button
    if (selects.length) {
        options = selects[0].getElementsByTagName('option');
        for (i = options.length - 1; i >= 0; i -= 1) {
            if (options[i].defaultSelected) {
                if (!options[i].selected) {
                    selects[0].value = options[i].value;
                }
                break;
            }
        }
    }

    // highlight the row of the referring stop
    function maybeHighlight(tr) {
        var as = tr.getElementsByTagName('a');
        if (as.length && as[0].href === document.referrer) {
            tr.className += ' referrer';
        }
    }

    if (document.referrer.indexOf('/stops/') > -1) {
        ths = document.getElementsByTagName('th');
        for (i = ths.length - 1; i >= 0; i -= 1) {
            maybeHighlight(ths[i].parentNode);
        }
    }
}());
