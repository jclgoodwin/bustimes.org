from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .models import Disruption


def disruption(request, id):
    disruption = get_object_or_404(Disruption, id=id)
    return HttpResponse(disruption.text, content_type='text/xml')
