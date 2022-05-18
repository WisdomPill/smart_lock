from rest_framework.serializers import ModelSerializer

from entry.models import Entry


class EntrySerializer(ModelSerializer):
    class Meta:
        model = Entry
        fields = ("key",)
