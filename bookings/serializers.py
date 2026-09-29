from rest_framework import serializers

from .models import Booking


class BookingCreateSerializer(serializers.Serializer):
    event = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class BookingSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "event", "event_title", "quantity", "total_price",
            "status", "created_at", "cancelled_at",
        ]
        read_only_fields = fields
