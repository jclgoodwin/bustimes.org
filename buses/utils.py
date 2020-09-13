import re
import socket
from django.conf import settings


def minify(template_source):
    """Alternative to django_template_minifier's minify function
    """
    if '<' in template_source:
        template_source = re.sub(r'(\n *)+', '\n', template_source)
        template_source = re.sub(r'({%.+%})\n+', r'\1', template_source)
    return template_source


def varnish_ban(url):
    if settings.VARNISH:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(settings.VARNISH)
        except socket.error:
            pass
        else:
            sock.sendall(f"BAN {url} HTTP/1.1\r\nHost: bustimes.org\r\n\r\n".encode())
        finally:
            sock.close()
