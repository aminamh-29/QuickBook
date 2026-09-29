from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from . import services
from .models import Booking
from .serializers import BookingCreateSerializer, BookingSerializer


class BookingViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    """Book tickets, view booking history, and cancel bookings."""

    serializer_class = BookingSerializer
    filterset_fields = ["status", "event"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Booking.objects.none()
        # Users only ever see their own bookings.
        return Booking.objects.select_related("event").filter(user=self.request.user)

    @extend_schema(request=BookingCreateSerializer, responses={201: BookingSerializer})
    def create(self, request):
        """Book tickets for an event."""
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = services.book_tickets(
            user=request.user,
            event_id=serializer.validated_data["event"],
            quantity=serializer.validated_data["quantity"],
        )
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: BookingSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a booking and release its seats."""
        booking = services.cancel_booking(user=request.user, booking_id=pk)
        return Response(BookingSerializer(booking).data)
