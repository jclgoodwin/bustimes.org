import re
from haystack.utils import default_get_identifier


def minify(template_source):
    template_source = re.sub(r'(\n *)+', '\n', template_source)
    template_source = re.sub(r'({%.+%})\n+', r'\1', template_source)
    return template_source

def get_identifier(obj_or_string):
    if isinstance(obj_or_string, basestring):
        return obj_or_string
    return default_get_identifier(obj_or_string)
