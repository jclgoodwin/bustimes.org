'use strict';

/*jslint
    browser: true
*/
/*global
    STOP_CODE
*/

(function() {
    if (!window.fetch) {
        return;
    }

    var search = window.location.search;

    function updateDepartures(event) {
        var newSearch;

        if (this instanceof HTMLFormElement) {
            var formData = new FormData(this);
            newSearch = '?' + new URLSearchParams(formData).toString();
        } else if (event.type === 'popstate') {
            newSearch = window.location.search;
        } else {
            newSearch = event.target.search;
        }

        if (search === newSearch) {
            return false;
        }

        var departures = document.getElementById('departures');

        departures.classList.add('loading');

        fetch('/stops/' + STOP_CODE + '/departures' + newSearch).then(function(response) {
            if (response.ok) {
                response.text().then(function(text) {
                    departures.outerHTML = text;
                    setUp();

                    search = newSearch;
                    if (window.location.search !== newSearch) {
                        if (newSearch) {
                            history.pushState(null, null, newSearch);
                        } else {
                            history.pushState(null, null, '/stops/' + STOP_CODE);
                        }
                    }
                });
            } else {
                departures.classList.remove('loading');
            }
        });
        return false;
    }

    function setUp() {
        var departures = document.getElementById('departures');
        var form = departures.querySelector('form');

        form.onsubmit = updateDepartures;

        // 'Now <' / 'Later >' links
        departures.querySelectorAll('p a').forEach(function(a) {
            a.onclick = updateDepartures;
        });
    }

    setUp();

    window.addEventListener('popstate', updateDepartures);

}());
