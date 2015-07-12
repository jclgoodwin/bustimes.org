from django.contrib import admin
from busstops.models import Region, AdminArea, District, Locality, StopPoint, Operator, Service, ServiceVersion


admin.site.register(Region)
admin.site.register(AdminArea)
admin.site.register(District)
admin.site.register(Locality)
admin.site.register(StopPoint)
admin.site.register(Operator)
admin.site.register(Service)
admin.site.register(ServiceVersion)
# admin.site.register(JourneyPatternSection)
# admin.site.register(JourneyPatternTimingLink)
# admin.site.register(OperatingProfile)
# admin.site.register(VehicleJourney)
