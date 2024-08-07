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
        var query = {
            limit: 100,
            name: params.term,
            published: true,
            offset: ((params.page | 1) - 1) * 100,
            delay: 250
        }
        return query;
    }

    function processResults(data) {
        return {
            results: data.results.map(function(item) {
                return {
                    id: item.id,
                    text: item.name,
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
        }
    });

    $('#id_colours').select2({
        allowClear: true,
        placeholder: "",
        ajax: {
            url: '/api/liveries/',
            data: data,
            processResults: processResults,
        },
        templateResult: formatLivery,
        templateSelection: formatLivery,
    });
})();
