from django.db.models import Prefetch
from django.shortcuts import render

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
    situations = Situation.objects.filter(id=id).prefetch_related(
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
