from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .models import Situation


def situation(request, id):
    situation = get_object_or_404(Situation, id=id)
    return HttpResponse(situation.data, content_type='text/xml')
