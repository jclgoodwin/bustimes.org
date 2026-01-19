import time
import requests
from django.conf import settings
from .models import Service


def get_popular_services():
    now = int(time.time() * 1000)
    day_ago = now - 86400 * 1000

    endpoint = f"https://umami.bustimes.org.uk/api/websites/{settings.UMAMI_WEBSITE_ID}/metrics"

    response = requests.get(
        endpoint,
        headers={"Authorization": f"Bearer {settings.UMAMI_TOKEN}"},
        params={
            "startAt": day_ago,
            "endAt": now,
            "type": "path",
            "timezone": "Europe/London",
            "search": "services",
            "limit": 10,
        },
        timeout=10,
    )

    data = response.json()

    # filter for /services/ paths and extract slugs
    slugs = [
        item["x"].split("/")[2]
        for item in data
        if item["x"].startswith("/services/") and len(item["x"].split("/")) >= 3
    ][:20]

    return Service.objects.filter(slug__in=slugs)
