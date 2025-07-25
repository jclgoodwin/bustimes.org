import xml.etree.ElementTree as ET

from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404
from django.utils.html import mark_safe
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import XmlLexer

from .models import Situation


def situations_index(request):
    situations = Situation.objects.filter(current=True).prefetch_related(
        Prefetch("consequence_set", to_attr="consequences"),
        "link_set",
        "validityperiod_set",
    )

    return render(
        request,
        "situations_index.html",
        {
            "situations": situations,
        },
    )


def situation(request, id):
    situation = get_object_or_404(
        Situation.objects.prefetch_related(
            Prefetch("consequence_set", to_attr="consequences"),
        ),
        id=id,
    )

    context = {}
    if situation.data:
        formatter = HtmlFormatter()

        xml = ET.XML(situation.data)
        ET.indent(xml)
        xml = ET.tostring(xml).decode()
        xml = mark_safe(highlight(xml, XmlLexer(), formatter))
        context["css"] = formatter.get_style_defs()
        context["xml"] = xml

    return render(
        request,
        "situations_index.html",
        {
            **context,
            "situation": situation,
            "situations": [situation],
        },
    )
