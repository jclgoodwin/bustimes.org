from .import_nx import Command as NatExpCommand


class Command(NatExpCommand):
    source_name = 'Kings Ferry'
    operators = ['KNGF', 'CLKL']
    url = 'https://kingsferry-tracker.utrackapps.com/api/eta/routes/{}/{}'
    sleep = 10
