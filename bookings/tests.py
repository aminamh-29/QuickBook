import threading
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import OperationalError, connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from bookings import services
from bookings.models import Booking
from config.exceptions import ServiceError
from events.models import Event, Vendor

User = get_user_model()


class BookingTestBase(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.vendor = Vendor.objects.create(name="V", contact_email="v@example.com")
        self.event = Event.objects.create(
            vendor=self.vendor, title="Concert", location="Ernakulam",
            start_time=timezone.now() + timedelta(days=5),
            price=Decimal("10.00"), total_seats=10, available_seats=10,
        )
        self.user = User.objects.create_user("alice", "a@example.com", "pass12345!")
        self.other = User.objects.create_user("bob", "b@example.com", "pass12345!")

    def seats(self):
        return Event.objects.get(pk=self.event.pk).available_seats


class BookingServiceTests(BookingTestBase):
    def test_booking_reduces_and_cancel_restores_seats(self):
        booking = services.book_tickets(user=self.user, event_id=self.event.pk, quantity=3)
        self.assertEqual(self.seats(), 7)
        self.assertEqual(booking.total_price, Decimal("30.00"))
        services.cancel_booking(user=self.user, booking_id=booking.pk)
        self.assertEqual(self.seats(), 10)

    def test_cannot_book_more_than_available(self):
        with self.assertRaises(ServiceError) as ctx:
            services.book_tickets(user=self.user, event_id=self.event.pk, quantity=11)
        self.assertEqual(ctx.exception.code, "insufficient_seats")
        self.assertEqual(self.seats(), 10)

    def test_invalid_quantities(self):
        for qty in (0, -1):
            with self.assertRaises(ServiceError):
                services.book_tickets(user=self.user, event_id=self.event.pk, quantity=qty)

    def test_cannot_book_past_or_inactive_event(self):
        Event.objects.filter(pk=self.event.pk).update(
            start_time=timezone.now() - timedelta(hours=1)
        )
        with self.assertRaises(ServiceError):
            services.book_tickets(user=self.user, event_id=self.event.pk, quantity=1)
        Event.objects.filter(pk=self.event.pk).update(
            start_time=timezone.now() + timedelta(days=1), is_active=False
        )
        with self.assertRaises(ServiceError):
            services.book_tickets(user=self.user, event_id=self.event.pk, quantity=1)

    def test_cannot_cancel_twice_or_someone_elses_booking(self):
        booking = services.book_tickets(user=self.user, event_id=self.event.pk, quantity=2)
        with self.assertRaises(ServiceError) as ctx:
            services.cancel_booking(user=self.other, booking_id=booking.pk)
        self.assertEqual(ctx.exception.status_code, 404)
        services.cancel_booking(user=self.user, booking_id=booking.pk)
        with self.assertRaises(ServiceError) as ctx:
            services.cancel_booking(user=self.user, booking_id=booking.pk)
        self.assertEqual(ctx.exception.code, "already_cancelled")
        self.assertEqual(self.seats(), 10)  # not restored twice


class BookingConcurrencyTests(BookingTestBase):
    def test_concurrent_bookings_never_oversell(self):
        """20 threads each want 1 seat of 10: at most 10 may succeed."""
        Event.objects.filter(pk=self.event.pk).update(total_seats=10, available_seats=10)
        n = 20
        barrier = threading.Barrier(n)
        results = []

        def worker():
            try:
                barrier.wait()
                for _ in range(20):  # retry on SQLite "table is locked"
                    try:
                        services.book_tickets(
                            user=self.user, event_id=self.event.pk, quantity=1
                        )
                        results.append("ok")
                        return
                    except OperationalError:
                        continue
                results.append("locked")
            except ServiceError:
                results.append("rejected")
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        booked = sum(
            Booking.objects.filter(event=self.event, status="confirmed")
            .values_list("quantity", flat=True)
        )
        self.assertLessEqual(booked, 10)
        self.assertEqual(self.seats(), 10 - booked)
        self.assertEqual(results.count("ok"), booked)
        self.assertGreaterEqual(self.seats(), 0)


class BookingApiTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")

    def test_requires_authentication(self):
        self.assertEqual(self.client.get("/api/bookings/").status_code, 401)
        self.assertEqual(self.client.get("/api/events/").status_code, 401)

    def test_book_cancel_history_flow(self):
        self.auth(self.user)
        r = self.client.post("/api/bookings/", {"event": self.event.pk, "quantity": 2}, format="json")
        self.assertEqual(r.status_code, 201)
        r2 = self.client.post("/api/bookings/", {"event": self.event.pk, "quantity": 0}, format="json")
        self.assertEqual(r2.status_code, 400)
        r3 = self.client.post("/api/bookings/", {"event": self.event.pk, "quantity": 99}, format="json")
        self.assertEqual(r3.status_code, 409)
        self.assertEqual(self.client.get("/api/bookings/").json()["count"], 1)
        self.assertEqual(self.client.post(f"/api/bookings/{r.json()['id']}/cancel/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/bookings/{r.json()['id']}/cancel/").status_code, 409)

    def test_cannot_see_or_cancel_others_bookings(self):
        booking = services.book_tickets(user=self.other, event_id=self.event.pk, quantity=1)
        self.auth(self.user)
        self.assertEqual(self.client.get("/api/bookings/").json()["count"], 0)
        self.assertEqual(self.client.post(f"/api/bookings/{booking.pk}/cancel/").status_code, 404)

    def test_event_search_and_filter(self):
        self.auth(self.user)
        r = self.client.get("/api/events/", {"search": "concert", "max_price": "20"})
        self.assertEqual(r.json()["count"], 1)
        r = self.client.get("/api/events/", {"min_price": "50"})
        self.assertEqual(r.json()["count"], 0)

    def test_event_location_filter(self):
        self.auth(self.user)
        r = self.client.get("/api/events/", {"location": "Ernakulam"})
        self.assertEqual(r.json()["count"], 1)
        r = self.client.get("/api/events/", {"location": "Kannur"})
        self.assertEqual(r.json()["count"], 0)
        # Only Kerala districts are accepted
        r = self.client.get("/api/events/", {"location": "Mumbai"})
        self.assertEqual(r.status_code, 400)
