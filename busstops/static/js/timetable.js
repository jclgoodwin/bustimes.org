'use strict';

/*jslint
    browser: true
*/

(function() {
    var divs = document.getElementsByTagName('div'),
        i,
        selects = document.getElementsByTagName('select'),
        options,
        ths;

    function fancify(div) {
        var ths = div.getElementsByTagName('th'),
            firstCellWidth,
            i;
        for (i = ths.length - 1; i >= 0; i -= 1) {
            if (ths[i].offsetWidth) {
                firstCellWidth = ths[i].offsetWidth + 'px';
                break;
            }
        }
        for (i = ths.length - 1; i >= 0; i -= 1) {
            ths[i].style.width = firstCellWidth;
            ths[i].style.marginLeft = '-' + firstCellWidth;
        }
        div.style.marginLeft = firstCellWidth;
        div.className += ' fancy';
    }

    function maybeHighlight(tr) {
        var as = tr.getElementsByTagName('a');
        if (as.length && as[0].href === document.referrer) {
            tr.style.display = 'table-row';
            tr.style.background = '#fe9';
        }
    }

    for (i = divs.length - 1; i >= 0; i -= 1) {
        if (divs[i].className === 'timetable-wrapper') {
            fancify(divs[i]);
        }
    }

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

    if (document.referrer.indexOf('/stops/') > -1) {
        ths = document.getElementsByTagName('th');
        for (i = ths.length - 1; i >= 0; i -= 1) {
            maybeHighlight(ths[i].parentNode);
        }
    }
}());
