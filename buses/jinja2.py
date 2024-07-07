from django.core.cache import cache
from django.template.defaultfilters import linebreaks, linebreaksbr
from django.templatetags.static import static
from django.urls import reverse
from django.utils.safestring import mark_safe
from jinja2 import Environment, nodes
from jinja2.ext import Extension

from busstops.templatetags.urlise import urlise
from vehicles.context_processors import _liveries_css_version

# based on https://jinja.palletsprojects.com/en/3.1.x/extensions/#cache


class FragmentCacheExtension(Extension):
    # a set of names that trigger the extension.
    tags = {"cache"}

    def __init__(self, environment):
        super().__init__(environment)

        # add the defaults to the environment
        environment.extend(fragment_cache_prefix="", fragment_cache=None)

    def parse(self, parser):
        # the first token is the token that started the tag.  In our case
        # we only listen to ``'cache'`` so this will be a name token with
        # `cache` as value.  We get the line number so that we can give
        # that line number to the nodes we create by hand.
        lineno = next(parser.stream).lineno

        # now we parse a single expression that is used as cache key.
        args = [parser.parse_expression()]

        # if there is a comma, the user provided a timeout.  If not use
        # None as second parameter.
        if parser.stream.skip_if("comma"):
            args.append(parser.parse_expression())
        else:
            args.append(nodes.Const(None))

        # now we parse the body of the cache block up to `endcache` and
        # drop the needle (which would always be `endcache` in that case)
        body = parser.parse_statements(["name:endcache"], drop_needle=True)

        # now return a `CallBlock` node that calls our _cache_support
        # helper method on this extension.
        return nodes.CallBlock(
            self.call_method("_cache_support", args), [], [], body
        ).set_lineno(lineno)

    def _cache_support(self, name, timeout, caller):
        """Helper callback."""
        key = self.environment.fragment_cache_prefix + name

        # try to load the block from the cache
        # if there is no fragment in the cache, render it and store
        # it in the cache.
        rv = cache.get(key)
        if rv is not None:
            return rv
        rv = caller()
        cache.set(key, rv, timeout)
        return rv


def environment(**options):
    env = Environment(extensions=[FragmentCacheExtension], **options)
    env.lstrip_blocks = True
    env.trim_blocks = True
    env.globals.update(
        {
            "static": static,
            "url": reverse,
            "liveries_css_version": _liveries_css_version,
            "urlise": urlise,
            "linebreaksbr": mark_safe(linebreaksbr),
            "linebreaks": mark_safe(linebreaks),
        }
    )
    return env
