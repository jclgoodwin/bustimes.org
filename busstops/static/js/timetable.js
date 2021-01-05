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
        var form = timetableWrapper.getElementsByTagName('form')[0],
            i,
            selects = form.getElementsByTagName('select'),
            ths;

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

        selects[0].onchange = function(event) {
            timetableWrapper.className = 'loading';
            reqwest('/services/' + SERVICE_ID + '/timetable?date=' + event.target.value, function(response) {
                timetableWrapper.className = '';
                timetableWrapper.innerHTML = response;
                doStuff();

                history.pushState(null, null, '?date=' + event.target.value);

            });
        };
    }

    doStuff();

    window.addEventListener('popstate', function() {
        var params = new URLSearchParams(window.location.search);
        var date = params.get('date');
        var url = '/services/' + SERVICE_ID + '/timetable';
        if (date) {
            url += '?date=' + date;
        }
        reqwest(url, function(response) {
            timetableWrapper.className = '';
            timetableWrapper.innerHTML = response;
            doStuff();
        });
    });
}());
