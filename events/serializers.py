from rest_framework import serializers

from .models import Event


class EventSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)

    class Meta:
        model = Event
        fields = [
            "id", "title", "description", "location", "start_time", "price",
            "total_seats", "available_seats", "vendor", "vendor_name",
        ]
        read_only_fields = fields
