from redis import from_url
from django.conf import settings
from .models import VehicleEdit, VehicleRevision, VehicleType, Livery


redis_client = from_url(settings.REDIS_URL)


def flush_redis():
    """For use in tests"""
    redis_client.flushall()


def get_vehicle_edit(vehicle, fields, now, request):
    edit = VehicleEdit(vehicle=vehicle, datetime=now)

    changed = False

    if request.user.is_authenticated:
        edit.user = request.user

    if 'fleet_number' in fields:
        if fields['fleet_number']:
            edit.fleet_number = fields['fleet_number']
        else:
            edit.fleet_number = f'-{vehicle.fleet_code or vehicle.fleet_number}'
        changed = True

    for field in ('fleet_number', 'reg', 'vehicle_type', 'branding', 'name', 'notes'):
        if field in fields and str(fields[field]) != str(getattr(vehicle, field)):
            if fields[field]:
                setattr(edit, field, fields[field])
            else:
                setattr(edit, field, f'-{getattr(vehicle, field)}')
            changed = True

    if 'spare_ticket_machine' in fields:
        if fields['spare_ticket_machine']:
            edit.notes = 'Spare ticket machine'
        elif edit.notes:
            edit.notes = f'-{edit.notes}'
        changed = True

    if 'withdrawn' in fields:
        edit.withdrawn = fields['withdrawn']
        changed = True

    changes = {}
    if 'previous_reg' in fields:
        changes['Previous reg'] = fields['previous_reg']
    if changes:
        edit.changes = changes
        changed = True

    edit.url = fields.get('url', '')
    if edit.url:
        changed = True

    if fields.get('colours'):
        if fields['colours'].isdigit():
            edit.livery_id = int(fields['colours'])
            if edit.livery_id != vehicle.livery_id:
                changed = True
        elif fields['colours']:
            edit.colours = fields['colours']
            if edit.colours != vehicle.colours:
                changed = True
    if fields.get('other_colour'):
        edit.colours = fields['other_colour']
        changed = True

    return edit, changed


def do_revisions(vehicles, data, user):
    revisions = [VehicleRevision(vehicle=vehicle, user=user, changes={}) for vehicle in vehicles]
    changed_fields = []

    # actually edit some vehicle fields, depending on how trusted the user is,
    # create a VehicleRevision record,
    # and remove fields from the 'data' dict so they're not part of any VehicleEdits created in the next step

    if user.trusted:

        if 'withdrawn' in data:
            to_value = 'Yes' if data['withdrawn'] else 'No'
            for revision in revisions:
                from_value = 'Yes' if revision.vehicle.withdrawn else 'No'
                revision.changes['withdrawn'] = f"-{from_value}\n+{to_value}"
                revision.vehicle.withdrawn = data['withdrawn']
            changed_fields.append('withdrawn')
            del data['withdrawn']

        if 'vehicle_type' in data:
            vehicle_type = VehicleType.objects.get(name=data['vehicle_type'])
            for revision in revisions:
                if revision.vehicle.vehicle_type_id != vehicle_type.id:
                    revision.from_type = revision.vehicle.vehicle_type
                    revision.to_type = vehicle_type
                    revision.vehicle.vehicle_type = vehicle_type
            changed_fields.append('vehicle_type')
            del data['vehicle_type']

        if 'colours' in data:
            if data['colours'].isdigit():
                livery = Livery.objects.get(id=data['colours'])
                for revision in revisions:
                    if revision.vehicle.livery_id != livery.id:
                        revision.from_livery = revision.vehicle.livery
                        revision.to_livery = livery
                        revision.vehicle.livery = livery
                        if revision.vehicle.colours:
                            revision.changes['colours'] = f"-{revision.vehicle.colours}\n+"
                            revision.vehicle.colours = ''
            else:
                to_colour = data.get('other_colour') or data['colours']
                for revision in revisions:
                    revision.from_livery = revision.vehicle.livery
                    revision.vehicle.livery = None
                    if revision.vehicle.colours != to_colour:
                        revision.changes['colours'] = f"-{revision.vehicle.colours}\n+{to_colour}"
                        revision.vehicle.colours = to_colour
            changed_fields += ['livery', 'colours']
            del data['colours']
            if 'other_colour' in data:
                del data['other_colour']

    return revisions, changed_fields


def do_revision(vehicle, data, user):
    (revision,), changed_fields = do_revisions((vehicle,), data, user)

    if user.trusted:
        if 'reg' in data:
            revision.changes['reg'] = f"-{vehicle.reg}\n+{data['reg']}"
            vehicle.reg = data['reg']
            changed_fields.append('reg')
            del data['reg']

        if 'branding' in data and data['branding'] == '':
            revision.changes['branding'] = f"-{vehicle.branding}\n+"
            vehicle.branding = ''
            changed_fields.append('branding')
            del data['branding']

    if user.is_staff:
        for field in ('notes', 'branding', 'name'):
            if field in data:
                from_value = getattr(vehicle, field)
                to_value = data[field]
                revision.changes[field] = f"-{from_value}\n+{to_value}"
                setattr(vehicle, field, to_value)
                changed_fields.append(field)
                del data[field]

    # operator has its own ForeignKey fields:

    if 'operator' in data:
        revision.from_operator = vehicle.operator
        revision.to_operator = data['operator']
        vehicle.operator = data['operator']
        changed_fields.append('operator')
        del data['operator']

    if changed_fields:
        vehicle.save(update_fields=changed_fields)

        return revision
