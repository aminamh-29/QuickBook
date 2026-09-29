from django.utils import timezone
from rest_framework import viewsets

from .filters import EventFilter
from .models import Event
from .serializers import EventSerializer


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """Browse, search and filter upcoming active events."""

    serializer_class = EventSerializer
    filterset_class = EventFilter
    search_fields = ["title", "description", "location", "vendor__name"]
    ordering_fields = ["start_time", "price", "title"]

    def get_queryset(self):
        return Event.objects.select_related("vendor").filter(
            is_active=True,
            vendor__is_active=True,
            start_time__gt=timezone.now(),
        )
