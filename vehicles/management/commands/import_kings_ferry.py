from busstops.models import Service
from .import_nx import sleep, RequestException, Command as NatExpCommand


class Command(NatExpCommand):
    source_name = 'Kings Ferry'
    operators = ['KNGF', 'CLKL']
    url = 'https://kingsferry-tracker.utrackapps.com/api/eta/routes/{}/{}'
    sleep = 10
