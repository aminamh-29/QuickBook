from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Vendor(models.Model):
    """Seller / event organizer. Managed by staff; vendors do not log in."""

    name = models.CharField(max_length=150)
    contact_email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Event(models.Model):
    vendor = models.ForeignKey(
        Vendor, on_delete=models.PROTECT, related_name="events"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total_seats = models.PositiveIntegerField()
    available_seats = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(available_seats__lte=F("total_seats")),
                name="available_seats_lte_total_seats",
            ),
            models.CheckConstraint(
                condition=Q(price__gte=0), name="event_price_non_negative"
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def is_bookable(self):
        return self.is_active and self.start_time > timezone.now()
