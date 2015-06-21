import csv
from busstops.models import Locality, StopPoint, AdminArea
from geoposition.fields import Geoposition

with open('Stops.csv', 'rb') as csv_file:
    csv_data = csv.reader(csv_file)
    csv_data.next() # skip title
    for row in csv_data:
        try:
            stop = StopPoint(
                atco_code=row[0],
                naptan_code=row[1],
                common_name=row[4],
                landmark=row[8],
                street=row[10],
                crossing=row[12],
                indicator=row[14],
                locality=Locality.objects.get(id=row[17]),
                suburb=row[23],
                location=Geoposition(row[30], row[29]),
                stop_type=row[31],
                bus_stop_type=row[32],
                timing_status=row[33],
                town=row[21],
                locality_centre=(row[25] == '1'),
                active=(row[42] == 'act'),
                admin_area=AdminArea.objects.get(id=row[37]),
                bearing=row[16]
                )
            stop.save()
        except Exception:
            print row
