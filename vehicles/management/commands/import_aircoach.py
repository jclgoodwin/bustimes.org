from .import_nx import Command as NatExpCommand


class Command(NatExpCommand):
    source_name = "Aircoach"
    operators = ["ie-663"]
    url = "https://tracker.aircoach.ie/api/eta/routes/{}/{}"
    sleep = 10

    def get_journey(self, item, vehicle):
        # reverse direction to aid matching of trips
        item["dir"] = "I" if item["dir"] == "O" else "O"

        return super().get_journey(item, vehicle)
