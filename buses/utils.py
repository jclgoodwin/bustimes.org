"""Small utility functions, used for overriding the default behaviour of third-party Django plugins
"""
import re
from haystack.utils import default_get_identifier


def minify(template_source):
    """Alternative to django_template_minifier's minify function
    """
    template_source = re.sub(r'(\n *)+', '\n', template_source)
    template_source = re.sub(r'({%.+%})\n+', r'\1', template_source)
    return template_source


def get_identifier(obj_or_string):
    """Alternative to django_haystack's get_identifier function,
    which doesn't mind underscores or hyphens in primary keys
    """
    if isinstance(obj_or_string, str):
        return obj_or_string
    return default_get_identifier(obj_or_string)
