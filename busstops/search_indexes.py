from haystack import indexes
from busstops.models import Locality, Operator, Service


class LocalityIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, model_attr='get_qualified_name')

    def get_model(self):
        return Locality

    def index_queryset(self, using=None):
        return self.get_model().objects.exclude(locality__isnull=True, stoppoint__isnull=True).distinct()

    def read_queryset(self, using=None):
        return self.get_model().objects.all()


class OperatorIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, model_attr='name')

    def get_model(self):
        return Operator

    def index_queryset(self, using=None):
        return self.get_model().objects.filter(service__current=True).distinct()

    def read_queryset(self, using=None):
        return self.get_model().objects.all()


class ServiceIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)

    def get_model(self):
        return Service

    def index_queryset(self, using=None):
        return self.get_model().objects.filter(current=True).prefetch_related('operator', 'stops', 'stops__locality').defer('stops__latlong', 'stops__locality__latlong').distinct()

    def read_queryset(self, using=None):
        return self.get_model().objects.all()
