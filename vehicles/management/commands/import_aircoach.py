from .import_nx import Command as NatExpCommand


class Command(NatExpCommand):
    source_name = 'Aircoach'
    operators = ['663']
    url = 'https://tracker.aircoach.ie/api/eta/routes/{}/{}'
    sleep = 10
