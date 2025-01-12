/*jslint browser: true*/

(function () {
    'use strict';


    function formatLivery(livery) {
        if (!livery.id) {
            return livery.text;
        }
        if (livery.css) {
            return $(
                '<div><div class="livery" style="background:'+ livery.css + '"></div>' + livery.text + '</div>'
            );
        }
        return $(
            '<div><div class="livery livery-'+ livery.id + '"></div>' + livery.text + '</div>'
        );
    }

    function data(params) {
        // return the query for the vehicle types/liveries API
        var query = {
            limit: 100,
            published: true,
            offset: ((params.page | 1) - 1) * 100,
        };
        if (params.term) {
            query.name__icontains = params.term;
        } else {
            var suggested = this.data("suggested");
            if (suggested) {
                query.id__in = this.data("suggested");
            } else {
                query.vehicle__operator = $('#id_operator').val();
            }
        }
        return query;
    }

    function processResults(data) {
        return {
            results: data.results.map(function(item) {
                var name = item.name;
                if (item.noc) {
                    name += " (" + item.noc + ")";
                }
                return {
                    id: item.id || item.noc,
                    text: name,
                    css: item.left_css
                };
            }),
            pagination: {
                more: data.next ? true : false
            }
        };
    }

    $('#id_vehicle_type').select2({
        allowClear: true,
        placeholder: "",
        ajax: {
            url: '/api/vehicletypes/',
            data: data,
            processResults: processResults,
            delay: 250
        },
    });

    $('#id_colours').select2({
        allowClear: true,
        placeholder: "",
        ajax: {
            url: '/api/liveries/',
            data: data,
            processResults: processResults,
            delay: 250
        },
        templateResult: formatLivery,
        templateSelection: formatLivery,
    });


    $('#id_operator').select2({
        allowClear: true,
        placeholder: "",
        ajax: {
            url: '/api/operators/',
            data: data,
            processResults: processResults,
            delay: 250
        },
        minimumInputLength: 1
    });

})();
