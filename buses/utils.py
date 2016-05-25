import re


def minify(template_source):
    template_source = re.sub(r'(\n *)+', '\n', template_source)
    template_source = re.sub(r'({%.+%})\n+', r'\1', template_source)
    return template_source
