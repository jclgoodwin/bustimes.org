import re


def minify(template_source):
   return re.sub(r'(\n *)+', '\n', template_source)
