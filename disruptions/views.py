from django.shortcuts import get_object_or_404, render
from .models import Situation


def situation(request, id):
    situation = get_object_or_404(Situation, id=id)

    return render(
        request,
        "situations.html",
        {
            "situations": [situation],
        },
    )
