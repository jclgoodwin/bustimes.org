(function () {

    var buttons = document.getElementsByTagName('button');

    buttons[0].onclick = function() {
        if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(function (p) {
                    var x = Math.round(p.coords.longitude * 1000 ) / 1000,
                        y = Math.round(p.coords.latitude * 1000 ) / 1000;
                    buttons[0].className += ' loading';
                    buttons[0].setAttribute('disabled', 'disabled')
                    buttons[0].innerHTML = 'Finding bus stops near ' + y + ', ' + x + '\u2026';
                    window.location.href = '/coordinates/' + y + ',' + x;
                });
        }
    }

})();
