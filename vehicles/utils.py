from .models import VehicleEdit


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
