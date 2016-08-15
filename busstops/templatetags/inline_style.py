"""https://github.com/jazzband/django-pipeline/issues/295"""

from __future__ import unicode_literals
import codecs

from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils.safestring import mark_safe
from django import template
from pipeline.templatetags import pipeline

register = template.Library()


class StylesheetNode(pipeline.StylesheetNode):
    def render_css(self, package, path):
        return self.render_individual_css(package, [path])

    def render_individual_css(self, package, paths, **kwargs):
        html = []
        for path in paths:
            with codecs.open(staticfiles_storage.path(path), 'r', 'utf-8') as open_file:
                html.append(open_file.read())
        return mark_safe('<style amp-custom>' + '\n'.join(html) + '</style>')


@register.tag
def inline_stylesheet(parser, token):
    """Template tag that mimics pipeline's stylesheet tag, but embeds
    the resulting CSS directly in the page.
    """
    name = token.split_contents()[0]
    return StylesheetNode(name)
