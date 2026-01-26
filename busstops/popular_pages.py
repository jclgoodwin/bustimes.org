from datetime import datetime, timedelta, timezone
import requests
from django.conf import settings
from .models import Service


def get_popular_services():
    now = datetime.now(tz=timezone.utc)
    day_ago = now - timedelta(days=1)

    endpoint = f"https://umami.bustimes.org.uk/api/websites/{settings.UMAMI_WEBSITE_ID}/metrics"

    response = requests.get(
        endpoint,
        headers={"Authorization": f"Bearer {settings.UMAMI_TOKEN}"},
        params={
            "startAt": int(day_ago.timestamp() * 1000),
            "endAt": int(now.timestamp() * 1000),
            "type": "path",
            "timezone": "UTC",
            "search": "services",
            "limit": 20,
        },
        timeout=10,
    )

    data = response.json()

    slugs = [item["x"].split("/")[2] for item in data]

    return Service.objects.with_line_names().filter(slug__in=slugs)
