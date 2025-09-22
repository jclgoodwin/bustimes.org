from .models import Calendar, CalendarDate


MODES = {
    0: "tram",
    2: "rail",
    3: "bus",
    4: "ferry",
    6: "cable car",
    200: "coach",
    76: "air",  # 1100
}


def get_calendars(feed, source) -> dict:
    calendars = {
        row.service_id: Calendar(
            mon=row.monday,
            tue=row.tuesday,
            wed=row.wednesday,
            thu=row.thursday,
            fri=row.friday,
            sat=row.saturday,
            sun=row.sunday,
            start_date=row.start_date,
            end_date=row.end_date,
            source=source,
        )
        for row in feed.calendar.itertuples()
    }

    calendar_dates = []

    if feed.calendar_dates is not None:
        for row in feed.calendar_dates.itertuples():
            operation = row.exception_type == 1
            # 1: operates, 2: does not operate

            if (calendar := calendars.get(row.service_id)) is None:
                calendar = Calendar(
                    start_date=row.date,  # dummy date
                )
                calendars[row.service_id] = calendar
            calendar_dates.append(
                CalendarDate(
                    calendar=calendar,
                    start_date=row.date,
                    end_date=row.date,
                    operation=operation,
                    special=operation,  # additional date of operation
                )
            )

    Calendar.objects.bulk_create(calendars.values())
    CalendarDate.objects.bulk_create(calendar_dates)

    return calendars
