from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from bookings.models import Booking
from events.models import Event


class SeedDemoTests(TestCase):
    def test_seed_demo_is_idempotent_and_consistent(self):
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)  # second run must not duplicate

        self.assertEqual(Event.objects.count(), 6)
        self.assertEqual(Booking.objects.count(), 7)
        comedy = Event.objects.get(title="Stand-up Comedy Night")
        self.assertEqual(comedy.available_seats, 0)
        for event in Event.objects.all():
            booked = sum(
                b.quantity for b in event.bookings.filter(status="confirmed")
            )
            self.assertEqual(event.total_seats - event.available_seats, booked)

    def test_seed_demo_creates_staff_login(self):
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)

        User = get_user_model()
        self.assertEqual(User.objects.filter(username="admin").count(), 1)
        self.assertTrue(
            self.client.login(username="admin", password="Admin@12345")
        )
        self.assertEqual(self.client.get("/dashboard/").status_code, 200)
