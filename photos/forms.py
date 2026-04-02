from django.forms import Form, URLField


class PhotoForm(Form):
    url = URLField(label="Flickr photo URL")
