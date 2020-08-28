from .models import VehicleEdit, VehicleRevision


def get_vehicle_edit(vehicle, fields, now, username):
    edit = VehicleEdit(vehicle=vehicle, datetime=now, username=username)

    for field in ('fleet_number', 'reg', 'vehicle_type', 'branding', 'name', 'notes'):
        if field in fields and str(fields[field]) != str(getattr(vehicle, field)):
            if fields[field]:
                setattr(edit, field, fields[field])
            else:
                setattr(edit, field, f'-{getattr(vehicle, field)}')

    changes = {}
    if 'depot' in fields:
        changes['Depot'] = fields['depot']
    if 'previous_reg' in fields:
        changes['Previous reg'] = fields['previous_reg'].upper()
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

    edit.withdrawn = fields.get('withdrawn')

    return edit


def do_revision(vehicle, data):
    changes = {}
    changed_fields = []

    if 'reg' in data:
        changes['reg'] = f"-{vehicle.reg}\n+{data['reg']}"
        vehicle.reg = data['reg']
        changed_fields.append('reg')
        del data['reg']

    for field in ('notes', 'branding', 'name'):
        if field in data and not data[field]:
            from_value = getattr(vehicle, field)
            to_value = data[field]
            changes[field] = f"-{from_value}\n+{to_value}"
            setattr(vehicle, field, to_value)
            changed_fields.append(field)
            del data[field]

    if 'depot' in data:
        if vehicle.data:
            from_depot = vehicle.data.get('Depot') or ''
            vehicle.data['Depot'] = data['depot']
        else:
            from_depot = ''
            vehicle.data = {'Depot': data['depot']}
        changes['depot'] = f"-{from_depot}\n+{data['depot']}"
        changed_fields.append('data')
        del data['depot']

    if changes or 'operator' in data:
        revision = VehicleRevision(
            vehicle=vehicle
        )

        if changes:
            revision.changes = changes

        if 'operator' in data:
            revision.from_operator = vehicle.operator
            revision.to_operator = data['operator']
            vehicle.operator = data['operator']
            changed_fields.append('operator')
            del data['operator']

        vehicle.save(update_fields=changed_fields)

        return revision
