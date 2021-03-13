from .models import Vehicle, VehicleEdit, VehicleRevision, VehicleType, Livery


def get_vehicle_edit(vehicle, fields, now, request):
    edit = VehicleEdit(vehicle=vehicle, datetime=now)

    if request.user.is_authenticated:
        edit.user = request.user

    for field in ('fleet_number', 'reg', 'vehicle_type', 'branding', 'name', 'notes'):
        if field in fields and str(fields[field]) != str(getattr(vehicle, field)):
            if fields[field]:
                setattr(edit, field, fields[field])
            else:
                setattr(edit, field, f'-{getattr(vehicle, field)}')

    if 'withdrawn' in fields:
        edit.withdrawn = fields['withdrawn']

    changes = {}
    if 'previous_reg' in fields:
        changes['Previous reg'] = fields['previous_reg']
    if changes:
        edit.changes = changes

    edit.url = fields.get('url', '')

    if fields.get('colours'):
        if fields['colours'].isdigit():
            edit.livery_id = fields['colours']
        elif fields['colours']:
            edit.colours = fields['colours']
    if fields.get('other_colour'):
        edit.colours = fields['other_colour']

    return edit


def do_revisions(vehicle_ids, data, user):
    vehicles = Vehicle.objects.filter(id__in=vehicle_ids)
    revisions = [VehicleRevision(vehicle=vehicle, user=user, changes={}) for vehicle in vehicles]
    changed_fields = []

    # actually edit some vehicle fields, depending on how trusted the user is,
    # create a VehicleRevision record,
    # and remove fields from the 'data' dict so they're not part of any VehicleEdits created in the next step

    if 'depot' in data:
        to_depot = data['depot']
        for revision in revisions:
            if revision.vehicle.data:
                from_depot = revision.vehicle.data.get('Depot') or ''
                if from_depot == to_depot:
                    continue
                if to_depot:
                    revision.vehicle.data['Depot'] = to_depot
                elif from_depot:
                    del revision.vehicle.data['Depot']
            else:
                from_depot = ''
                revision.vehicle.data = {'Depot': to_depot}
            revision.changes['depot'] = f"-{from_depot}\n+{to_depot}"
        changed_fields.append('data')
        del data['depot']

    if user.trusted:

        if data.get('withdrawn'):
            for revision in revisions:
                revision.vehicle.withdrawn = True
                revision.changes['withdrawn'] = "-No\n+Yes"
            changed_fields.append('withdrawn')
            del data['withdrawn']

        for field in ('notes', 'branding'):
            if field in data and not data[field]:
                to_value = data[field]
                for revision in revisions:
                    from_value = getattr(revision.vehicle, field)
                    if from_value != to_value:
                        revision.changes[field] = f"-{from_value}\n+{to_value}"
                        setattr(revision.vehicle, field, to_value)
                changed_fields.append(field)
                del data[field]

        if 'vehicle_type' in data:
            vehicle_type = VehicleType.objects.get(name=data['vehicle_type'])
            for revision in revisions:
                if revision.vehicle.vehicle_type_id != vehicle_type.id:
                    revision.from_type = revision.vehicle.vehicle_type
                    revision.to_type = vehicle_type
                    revision.vehicle.vehicle_type = vehicle_type
            changed_fields.append('vehicle_type')
            del data['vehicle_type']

        if 'colours' in data and data['colours'].isdigit():
            livery = Livery.objects.get(id=data['colours'])
            for revision in revisions:
                if revision.vehicle.livery_id != livery.id:
                    revision.from_livery = revision.vehicle.livery
                    revision.to_livery = livery
                    revision.vehicle.livery = livery
            changed_fields.append('livery')
            del data['colours']

    if 'operator' in data:
        assert False
        for revision in revisions:
            revision.from_operator_id = revision.vehicle.operator_id
            revision.to_operator = data['operator']
            revision.vehicle.operator = data['operator']
        changed_fields.append('operator')
        del data['operator']

    revisions = [revision for revision in revisions if str(revision)]

    return revisions, changed_fields


def do_revision(vehicle, data, user):
    changes = {}
    changed_fields = []

    if user.trusted:
        if 'reg' in data:
            changes['reg'] = f"-{vehicle.reg}\n+{data['reg']}"
            vehicle.reg = data['reg']
            changed_fields.append('reg')
            del data['reg']

        if 'withdrawn' in data:
            from_value = 'Yes' if vehicle.withdrawn else 'No'
            to_value = 'Yes' if data['withdrawn'] else 'No'
            changes['withdrawn'] = f"-{from_value}\n+{to_value}"
            vehicle.withdrawn = data['withdrawn']
            changed_fields.append('withdrawn')
            del data['withdrawn']

    if user.is_staff:
        for field in ('notes', 'branding', 'name'):
            if field in data:
                from_value = getattr(vehicle, field)
                to_value = data[field]
                changes[field] = f"-{from_value}\n+{to_value}"
                setattr(vehicle, field, to_value)
                changed_fields.append(field)
                del data[field]

    if 'depot' in data:
        if vehicle.data:
            from_depot = vehicle.data.get('Depot') or ''
            if data['depot']:
                vehicle.data['Depot'] = data['depot']
            elif from_depot:
                del vehicle.data['Depot']
        else:
            from_depot = ''
            vehicle.data = {'Depot': data['depot']}
        changes['depot'] = f"-{from_depot}\n+{data['depot']}"
        changed_fields.append('data')
        del data['depot']

    revision = VehicleRevision(
        vehicle=vehicle,
        user=user
    )
    if changes:
        revision.changes = changes

    if 'operator' in data:
        revision.from_operator = vehicle.operator
        revision.to_operator = data['operator']
        vehicle.operator = data['operator']
        changed_fields.append('operator')
        del data['operator']

    if user.trusted:
        if 'vehicle_type' in data:
            vehicle_type = VehicleType.objects.get(name=data['vehicle_type'])
            revision.from_type = vehicle.vehicle_type
            revision.to_type = vehicle_type
            vehicle.vehicle_type = vehicle_type
            changed_fields.append('vehicle_type')
            del data['vehicle_type']

        if 'colours' in data and data['colours'].isdigit():
            livery = Livery.objects.get(id=data['colours'])
            revision.from_livery = vehicle.livery
            revision.to_livery = livery
            vehicle.livery = livery
            changed_fields.append('livery')
            del data['colours']

    if changed_fields:
        vehicle.save(update_fields=changed_fields)

        return revision
