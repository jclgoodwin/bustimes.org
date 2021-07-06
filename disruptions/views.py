import xml.etree.cElementTree as ET
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from busstops.models import DataSource
from .management.commands.import_siri_sx import handle_item
from .models import Situation


def situation(request, id):
    situation = get_object_or_404(Situation, id=id)
    return HttpResponse(situation.data, content_type='text/xml')


def siri_sx(request):
    source = DataSource.objects.get(name='Transport for the North')
    iterator = ET.iterparse(request)
    situation_ids = []
    for _, element in iterator:
        if element.tag[:29] == '{http://www.siri.org.uk/siri}':
            element.tag = element.tag[29:]
            if element.tag == 'SubscriptionRef':
                subscription_ref = element.text
            if element.tag == 'PtSituationElement':
                situation_ids.append(handle_item(element, source))
                element.clear()

    if subscription_ref != source.settings.get('subscription_ref'):
        source.settings['subscription_ref'] = subscription_ref
        source.save(update_fields=['settings'])
        source.situation_set.filter(current=True).exclude(id__in=situation_ids).update(current=False)
