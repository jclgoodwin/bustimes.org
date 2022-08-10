from .import_megabus import Command as MegabusCommand


class Command(MegabusCommand):
    source_name = "National Express"
    operators = ["NATX"]
    sleep = 3
    livery = 643
