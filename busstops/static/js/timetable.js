'use strict';

/*jslint
    browser: true
*/
/*global
    reqwest, SERVICE_ID
*/

(function() {
    var timetableWrapper = document.getElementById('timetable');

    function doStuff() {
        // highlight the row of the referring stop
        function maybeHighlight(tr) {
            var as = tr.getElementsByTagName('a');
            if (as.length && as[0].href === document.referrer) {
                tr.className += ' referrer';
            }
        }

        if (document.referrer.indexOf('/stops/') > -1) {
            var ths = document.getElementsByTagName('th');
            for (var i = ths.length - 1; i >= 0; i -= 1) {
                maybeHighlight(ths[i].parentNode);
            }
        }

        var selects = timetableWrapper.getElementsByTagName('select');
        if (selects.length) {
            selects[0].onchange = function(event) {
                timetableWrapper.className = 'loading';
                var search = '?date=' + event.target.value;
                reqwest('/services/' + SERVICE_ID + '/timetable' + search, function(response) {
                    timetableWrapper.className = '';
                    timetableWrapper.innerHTML = response;
                    doStuff();
                    history.pushState(null, null, search);
                });
            };
        }
    }

    doStuff();

    window.addEventListener('popstate', function() {
        var url = '/services/' + SERVICE_ID + '/timetable';
        if (window.location.search) {
            url += window.location.search;
        }
        timetableWrapper.className = 'loading';
        reqwest(url, function(response) {
            timetableWrapper.className = '';
            timetableWrapper.innerHTML = response;
            doStuff();
        });
    });
}());
