import hashlib
import requests

from django.conf import settings
from django.core.files.base import ContentFile
from .models import Photo


def get_sha1(content):
    sha1 = hashlib.sha1(usedforsecurity=False)
    sha1.update(content)
    return sha1.hexdigest()


def add_flickr_photo(url, vehicle, request):
    photo_id = url.split("/photos/", 1)[1].split("/")[1]
    photo = Photo()
    session = requests.Session()
    session.params = {
        "format": "json",
        "api_key": settings.FLICKR_API_KEY,
        "photo_id": photo_id,
        "nojsoncallback": 1,
    }
    info = session.get(
        "https://api.flickr.com/services/rest",
        params={"method": "flickr.photos.getInfo"},
    ).json()
    photo.url = info["photo"]["urls"]["url"][0]["_content"]
    photo.credit = (
        info["photo"]["owner"]["realname"] or info["photo"]["owner"]["username"]
    )
    photo.caption = info["photo"]["title"]["_content"]
    sizes = session.get(
        "https://api.flickr.com/services/rest",
        params={"method": "flickr.photos.getSizes"},
    ).json()
    url = sizes["sizes"]["size"][-1]["source"]
    original = session.get(url)
    photo.image.save(get_sha1(original.content) + ".jpg", ContentFile(original.content))
    photo.user = request.user
    photo.save()
    photo.vehicles.add(vehicle)
