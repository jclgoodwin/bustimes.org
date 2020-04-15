"""Small utility functions, used for overriding the default behaviour of third-party Django plugins
"""
import re


def minify(template_source):
    """Alternative to django_template_minifier's minify function
    """
    template_source = re.sub(r'(\n *)+', '\n', template_source)
    template_source = re.sub(r'({%.+%})\n+', r'\1', template_source)
    return template_source
