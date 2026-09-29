from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings import services as booking_services
from events.models import Event, Vendor

User = get_user_model()

PROTECTED = [
    "dashboard:home", "dashboard:vendor_list", "dashboard:vendor_add",
    "dashboard:event_list", "dashboard:event_add", "dashboard:user_list",
]


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", "s@example.com", "pass12345!", is_staff=True)
        self.customer = User.objects.create_user("cust", "c@example.com", "pass12345!")

    def test_anonymous_redirected_to_login(self):
        for name in PROTECTED:
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertTrue(r.url.startswith(reverse("dashboard:login")), name)

    def test_non_staff_forbidden(self):
        self.client.force_login(self.customer)
        for name in PROTECTED:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)
        detail = reverse("dashboard:user_detail", args=[self.customer.pk])
        self.assertEqual(self.client.get(detail).status_code, 403)

    def test_staff_allowed(self):
        self.client.force_login(self.staff)
        for name in PROTECTED:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_login_page_rejects_non_staff_and_accepts_staff(self):
        url = reverse("dashboard:login")
        bad = self.client.post(url, {"username": "cust", "password": "pass12345!"})
        self.assertEqual(bad.status_code, 200)  # re-rendered with error
        self.assertNotIn("_auth_user_id", self.client.session)
        ok = self.client.post(url, {"username": "staff", "password": "pass12345!"})
        self.assertRedirects(ok, reverse("dashboard:home"))

    def test_home_counts(self):
        vendor = Vendor.objects.create(name="V", contact_email="v@example.com")
        Event.objects.create(
            vendor=vendor, title="E", location="Kollam",
            start_time=timezone.now() + timedelta(days=1),
            price=1, total_seats=5, available_seats=5,
        )
        self.client.force_login(self.staff)
        stats = {label: n for label, n, _ in self.client.get(reverse("dashboard:home")).context["stats"]}
        self.assertEqual(stats["Total Customers"], 1)  # staff excluded
        self.assertEqual(stats["Total Vendors"], 1)
        self.assertEqual(stats["Total Events"], 1)
        self.assertEqual(stats["Total Bookings"], 0)


class DashboardManagementTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", "s@example.com", "pass12345!", is_staff=True)
        self.client.force_login(self.staff)
        self.vendor = Vendor.objects.create(name="Acme", contact_email="a@example.com")

    def event_payload(self, **over):
        data = {
            "vendor": self.vendor.pk, "title": "Show", "description": "",
            "location": "Ernakulam", "start_time": (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
            "price": "12.50", "total_seats": 10, "is_active": "on",
        }
        data.update(over)
        return data

    def test_event_location_must_be_a_kerala_district(self):
        url = reverse("dashboard:event_add")
        r = self.client.post(url, self.event_payload(location="Mumbai"))
        self.assertEqual(r.status_code, 200)  # form redisplayed with an error
        self.assertFalse(Event.objects.exists())
        r = self.client.post(url, self.event_payload(location="Kannur"))
        self.assertRedirects(r, reverse("dashboard:event_list"))
        self.assertEqual(Event.objects.get().location, "Kannur")

    def test_event_list_location_filter(self):
        for loc in ("Kannur", "Kannur", "Wayanad"):
            Event.objects.create(
                vendor=self.vendor, title="E", location=loc,
                start_time=timezone.now() + timedelta(days=1),
                price=Decimal("5"), total_seats=5, available_seats=5,
            )
        r = self.client.get(reverse("dashboard:event_list"), {"location": "Kannur"})
        self.assertEqual(r.context["paginator"].count, 2)

    def test_vendor_create_and_update(self):
        r = self.client.post(reverse("dashboard:vendor_add"), {
            "name": "New", "contact_email": "n@example.com", "phone": "1", "address": "x", "is_active": "on",
        })
        self.assertRedirects(r, reverse("dashboard:vendor_list"))
        vendor = Vendor.objects.get(name="New")
        self.client.post(reverse("dashboard:vendor_edit", args=[vendor.pk]), {
            "name": "Renamed", "contact_email": "n@example.com",
        })
        vendor.refresh_from_db()
        self.assertEqual(vendor.name, "Renamed")
        self.assertFalse(vendor.is_active)

    def test_event_create_sets_available_seats(self):
        self.client.post(reverse("dashboard:event_add"), self.event_payload())
        event = Event.objects.get(title="Show")
        self.assertEqual((event.total_seats, event.available_seats), (10, 10))

    def test_event_total_seats_edit_respects_bookings(self):
        self.client.post(reverse("dashboard:event_add"), self.event_payload())
        event = Event.objects.get(title="Show")
        customer = User.objects.create_user("c", "c@example.com", "pass12345!")
        booking_services.book_tickets(user=customer, event_id=event.pk, quantity=4)
        url = reverse("dashboard:event_edit", args=[event.pk])

        # Cannot drop below the 4 booked seats
        bad = self.client.post(url, self.event_payload(total_seats=3))
        self.assertEqual(bad.status_code, 200)
        self.assertIn("total_seats", bad.context["form"].errors)

        # Raising the total raises availability by the same amount
        self.client.post(url, self.event_payload(total_seats=15))
        event.refresh_from_db()
        self.assertEqual((event.total_seats, event.available_seats), (15, 11))

    def test_event_search_filter_and_pagination(self):
        other = Vendor.objects.create(name="Other", contact_email="o@example.com")
        for i in range(12):
            Event.objects.create(
                vendor=self.vendor if i % 2 else other, title=f"Party {i}", location="Ernakulam",
                start_time=timezone.now() + timedelta(days=i + 1),
                price=Decimal("5"), total_seats=5, available_seats=5,
            )
        url = reverse("dashboard:event_list")
        page1 = self.client.get(url)
        self.assertEqual(len(page1.context["events"]), 10)
        self.assertEqual(len(self.client.get(url, {"page": 2}).context["events"]), 2)
        self.assertEqual(len(self.client.get(url, {"q": "Party 11"}).context["events"]), 1)
        by_vendor = self.client.get(url, {"vendor": self.vendor.pk})
        self.assertEqual(by_vendor.context["paginator"].count, 6)

    def test_user_detail_tree_search(self):
        root = User.objects.create_user("root", "r@example.com", "pass12345!")
        from referrals import services as ref
        for name in ("alpha", "beta", "gamma"):
            ref.create_user_in_tree(
                referrer=root, username=name, email=f"{name}@example.com", password="pass12345!"
            )
        r = self.client.get(reverse("dashboard:user_detail", args=[root.pk]), {"q": "gam"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual([u.username for u, _ in r.context["matches"]], ["gamma"])
        self.assertEqual(r.context["stats"]["total_team"], 3)
