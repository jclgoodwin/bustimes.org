from haystack import indexes
from django.db.models import Q
from busstops.models import Locality, Place, Operator, Service


class LocalityIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, model_attr='get_qualified_name')

    def get_model(self):
        return Locality

    def index_queryset(self, using=None):
        return self.get_model().objects.filter(
            Q(stoppoint__active=True) |
            Q(locality__stoppoint__active=True)
        ).defer('latlong').distinct()

    def read_queryset(self, using=None):
        return self.get_model().objects.all().defer('latlong')


class PlaceIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, model_attr='name')

    def get_model(self):
        return Place

    def index_queryset(self, using=None):
        return self.get_model().objects.all().defer('latlong', 'polygon')

    def read_queryset(self, using=None):
        return self.get_model().objects.all().defer('latlong', 'polygon')


class OperatorIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, model_attr='name')

    def get_model(self):
        return Operator

    def index_queryset(self, using=None):
        return self.get_model().objects.filter(service__current=True).distinct()

    def read_queryset(self, using=None):
        return self.get_model().objects.all()


class ServiceIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True, boost=0.8)
    name = indexes.CharField(use_template=True, boost=1.2)

    def get_model(self):
        return Service

    def index_queryset(self, using=None):
        return self.get_model().objects.filter(current=True).prefetch_related(
            'operator', 'stops', 'stops__locality'
        ).defer('stops__latlong', 'stops__locality__latlong').distinct()

    def read_queryset(self, using=None):
        return self.get_model().objects.all()
