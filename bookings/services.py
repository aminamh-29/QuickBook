"""Booking business logic.

Seat accuracy relies on locking the event row for the duration of the
transaction, so concurrent requests are serialised per event.
"""
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from config.exceptions import ConflictError, NotFoundError, ServiceError
from events.models import Event

from .models import Booking


def book_tickets(*, user, event_id, quantity):
    """Book ``quantity`` tickets for ``event_id`` and reduce available seats."""
    if not isinstance(quantity, int) or quantity < 1:
        raise ServiceError("Quantity must be a positive integer.", code="invalid_quantity")

    with transaction.atomic():
        try:
            event = (
                Event.objects.select_for_update()
                .select_related("vendor")
                .get(pk=event_id)
            )
        except Event.DoesNotExist:
            raise NotFoundError("Event not found.", code="event_not_found")

        if not event.is_active or not event.vendor.is_active:
            raise ServiceError("This event is not available for booking.", code="event_inactive")
        if event.start_time <= timezone.now():
            raise ServiceError("This event has already started or ended.", code="event_past")
        if quantity > event.available_seats:
            raise ConflictError(
                f"Only {event.available_seats} seat(s) left.", code="insufficient_seats"
            )

        event.available_seats = F("available_seats") - quantity
        event.save(update_fields=["available_seats"])
        return Booking.objects.create(
            user=user,
            event=event,
            quantity=quantity,
            total_price=event.price * quantity,
        )


def cancel_booking(*, user, booking_id):
    """Cancel ``user``'s booking and give its seats back to the event."""
    with transaction.atomic():
        # Look up the booking without a lock first to learn its event, then
        # lock in the same order as ``book_tickets`` (event before booking).
        try:
            event_id = Booking.objects.values_list("event_id", flat=True).get(
                pk=booking_id, user=user
            )
        except Booking.DoesNotExist:
            # Same response for missing and foreign bookings: no id probing.
            raise NotFoundError("Booking not found.", code="booking_not_found")

        event = Event.objects.select_for_update().get(pk=event_id)
        booking = Booking.objects.select_for_update().get(pk=booking_id)

        if booking.status == Booking.Status.CANCELLED:
            raise ConflictError("Booking is already cancelled.", code="already_cancelled")
        if event.start_time <= timezone.now():
            raise ServiceError(
                "Bookings for past events cannot be cancelled.", code="event_past"
            )

        booking.status = Booking.Status.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.save(update_fields=["status", "cancelled_at"])

        event.available_seats = F("available_seats") + booking.quantity
        event.save(update_fields=["available_seats"])
        return booking
