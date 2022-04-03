'use strict';

/*jslint
    browser: true
*/
/*global
    reqwest, SERVICE_ID, fusetag
*/

(function() {
    var timetableWrapper = document.getElementById('timetable');

    // highlight the row of the referring stop
    function maybeHighlight(tr) {
        var as = tr.getElementsByTagName('a');
        if (as.length && as[0].href === document.referrer) {
            tr.className += ' referrer';
        }
    }

    function doStuff() {
        if (document.referrer.indexOf('/stops/') > -1) {
            var ths = document.getElementsByTagName('th');
            for (var i = ths.length - 1; i >= 0; i -= 1) {
                maybeHighlight(ths[i].parentNode);
            }
        }

        // load timetable for a particular date without loading the rest of the page
        var select = document.getElementById('id_date');
        if (select) {
            select.onchange = function(event) {
                timetableWrapper.className = 'loading';
                var newSearch = '?date=' + event.target.value;
                reqwest('/services/' + SERVICE_ID + '/timetable' + newSearch, function(response) {
                    timetableWrapper.className = '';
                    timetableWrapper.innerHTML = response;
                    doStuff();
                    search = newSearch;
                    history.pushState(null, null, newSearch);
                    fusetag.registerZone('services-incontent');
                });
            };
        }
    }

    doStuff();

    var search  = window.location.search;

    window.addEventListener('popstate', function() {
        // handle back/forward navigation
        if (search !== window.location.search) {
            search = window.location.search;
            var url = '/services/' + SERVICE_ID + '/timetable';
            if (search) {
                url += search;
            }
            timetableWrapper.className = 'loading';
            reqwest(url, function(response) {
                timetableWrapper.className = '';
                timetableWrapper.innerHTML = response;
                doStuff();
                fusetag.registerZone('services-incontent');
            });
        }
    });
}());
