jQuery(document).ready(function($) {
    $('#id_text_colour').on('input', function(e) {
        $('.readonly svg text').attr('fill', e.target.value);
    });

    $('#id_stroke_colour').on('input', function(e) {
        $('.readonly svg text').attr('style', 'stroke:' + e.target.value + ';stroke-width:3px;paint-order:stroke');
    });


    $('#id_left_css').on('input', function(e) {
        $('.field-left .readonly svg').attr('style', 'line-height:24px;font-size:24px;background:' + e.target.value);
    });


    $('#id_right_css').on('input', function(e) {
        $('.field-right .readonly svg').attr('style', 'line-height:24px;font-size:24px;background:' + e.target.value);
    });
});
