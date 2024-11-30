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
        if (document.querySelectorAll && document.referrer.indexOf('/stops/') > -1) {
            var referrer = document.referrer.split('/stops/')[1];
            referrer = referrer.split('?')[0];
            if (referrer) {
                // highlight the row of the referring stop
                document.querySelectorAll('tr th a[href="/stops/' + referrer + '"]').forEach(function(a) {
                    a.parentNode.parentNode.className += ' referrer';
                });
            }
        }

        // load timetable for a particular date without loading the rest of the page
        if (timetableWrapper) {
            var timetableForm = timetableWrapper.querySelector('form');
        }
        if (timetableForm) {
            timetableForm.onchange = function() {
                if (typeof URLSearchParams === "undefined" || typeof FormData === "undefined") { // old browser
                    timetableForm.submit();
                    return;
                }

                timetableWrapper.className = 'loading';

                var formData = new FormData(timetableForm);
                var newSearch = '?' + new URLSearchParams(formData).toString();
                reqwest('/services/' + SERVICE_ID + '/timetable' + newSearch, function(response) {
                    timetableWrapper.className = '';
                    timetableWrapper.innerHTML = response;
                    doStuff();
                    search = newSearch;
                    history.pushState(null, "", newSearch);
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
            });
        }
    });
}());
