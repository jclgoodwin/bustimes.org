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

    var search = window.location.search,
        now;

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

        if (newSearch === now) {
            newSearch = search;  // search may be ''
        }

        var departures = document.getElementById('departures');

        departures.classList.add('loading');

        fetch('/stops/' + STOP_CODE + '/departures' + newSearch).then(function(response) {
            if (response.ok) {
                response.text().then(function(text) {
                    departures.outerHTML = text;

                    search = newSearch;

                    setUp();

                    if (window.location.search !== newSearch) {
                        if (newSearch) {
                            history.pushState(null, "", newSearch);
                        } else {
                            history.pushState(null, "", '/stops/' + STOP_CODE);
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
        var submitButton = form.querySelector('input[type=submit]')

        form.addEventListener("input", function() {
            if (submitButton.value !== "Go") {
                submitButton.value = "Go";
                submitButton.title = "";
                submitButton.ariaLabel = null;
            }
        })

        var formData = new FormData(form);

        now = '?' + new URLSearchParams(formData).toString();

        form.onsubmit = updateDepartures;

        // 'Now <' / 'Later >' links
        departures.querySelectorAll('p a').forEach(function(a) {
            a.onclick = updateDepartures;
        });
    }

    setUp();

    window.addEventListener('popstate', updateDepartures);

}());
