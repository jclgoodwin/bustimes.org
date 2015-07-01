(function () {

    var buttons = document.getElementsByTagName('button');

    buttons[0].onclick = function() {
        if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(function (p) {
                    window.location.href = '/coordinates/' + p.coords.latitude + ',' + p.coords.longitude;
                });
        }
    }

})();
