"""Populate the database with demo customers, vendors, events and bookings.

Safe to run repeatedly: existing demo rows are reused, and bookings are only
created when there are none yet. Admin credentials are read from environment
variables and the admin account is created or updated when the command runs.
"""

import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from bookings.services import book_tickets, cancel_booking
from events.models import Event, Vendor
from referrals.services import create_user_in_tree, get_referrer_by_code

User = get_user_model()

DEMO_PASSWORD = "Demo@12345"

# Configure these in Render Environment Variables.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

VENDORS = [
    ("Sunset Live Events", "hello@sunsetlive.example", "555-0101", "12 Harbor Rd"),
    ("City Arts Collective", "info@cityarts.example", "555-0102", "40 Gallery St"),
    ("TechConf Group", "team@techconf.example", "555-0103", "9 Innovation Way"),
]

# (vendor, title, location, days from now, price, seats)
EVENTS = [
    ("Sunset Live Events", "Rock Night", "Ernakulam", 5, 45, 100),
    ("Sunset Live Events", "Jazz Under the Stars", "Kozhikode", 12, 60, 40),
    ("City Arts Collective", "Modern Art Expo", "Thrissur", 8, 20, 200),
    ("City Arts Collective", "Stand-up Comedy Night", "Thiruvananthapuram", 3, 25, 5),
    ("TechConf Group", "Django Developers Summit", "Ernakulam", 20, 150, 300),
    ("TechConf Group", "AI Workshop", "Kannur", 15, 90, 30),
]

# (username, phone, username of the referrer or None for a new tree root)
CUSTOMERS = [
    ("alice", "555-1001", None),
    ("bob", "555-1002", "alice"),
    ("carol", "555-1003", "alice"),
    ("dave", "555-1004", "alice"),
    ("erin", "555-1005", "alice"),
    ("frank", "555-1006", "bob"),
    ("grace", "555-1007", None),
    ("heidi", "555-1008", "grace"),
]


class Command(BaseCommand):
    help = "Create demo customers, referral trees, vendors, events and bookings."

    @transaction.atomic
    def handle(self, *args, **options):
        if not ADMIN_PASSWORD:
            raise CommandError(
                "Set the ADMIN_PASSWORD environment variable before running "
                "seed_demo. Configure it in Render Environment Variables."
            )

        vendors = {}
        for name, email, phone, address in VENDORS:
            vendors[name], _ = Vendor.objects.get_or_create(
                name=name,
                defaults={
                    "contact_email": email,
                    "phone": phone,
                    "address": address,
                },
            )

        now = timezone.now()
        events = {}
        for vendor, title, location, days, price, seats in EVENTS:
            events[title], _ = Event.objects.get_or_create(
                title=title,
                defaults={
                    "vendor": vendors[vendor],
                    "description": f"{title} - demo event.",
                    "location": location,
                    "start_time": now + timedelta(days=days),
                    "price": price,
                    "total_seats": seats,
                    "available_seats": seats,
                },
            )

        users = {}
        for username, phone, referrer_name in CUSTOMERS:
            user = User.objects.filter(username=username).first()

            if user is None:
                referrer = (
                    get_referrer_by_code(users[referrer_name].referral_code)
                    if referrer_name
                    else None
                )
                user = create_user_in_tree(
                    referrer=referrer,
                    username=username,
                    email=f"{username}@example.com",
                    phone=phone,
                    password=DEMO_PASSWORD,
                )

            users[username] = user

        if not Booking.objects.exists():
            self._create_bookings(users, events)

        # Create the administrator or update the existing account.
        admin_user = User.objects.filter(username=ADMIN_USERNAME).first()

        if admin_user is None:
            User.objects.create_superuser(
                username=ADMIN_USERNAME,
                email=ADMIN_EMAIL,
                password=ADMIN_PASSWORD,
            )
            self.stdout.write(self.style.SUCCESS("Dashboard administrator created."))
        else:
            admin_user.email = ADMIN_EMAIL
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.set_password(ADMIN_PASSWORD)
            admin_user.save()
            self.stdout.write(
                self.style.SUCCESS("Dashboard administrator credentials updated.")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready: {len(users)} customers, "
                f"{len(vendors)} vendors, {len(events)} events. "
                f"Dashboard username: {ADMIN_USERNAME}"
            )
        )

    @staticmethod
    def _create_bookings(users, events):
        def book(username, title, quantity):
            return book_tickets(
                user=users[username],
                event_id=events[title].id,
                quantity=quantity,
            )

        book("alice", "Rock Night", 2)
        book("alice", "Django Developers Summit", 1)
        book("bob", "Jazz Under the Stars", 4)
        book("carol", "Modern Art Expo", 3)
        book("dave", "Stand-up Comedy Night", 5)

        cancelled = book("erin", "AI Workshop", 2)
        cancel_booking(user=users["erin"], booking_id=cancelled.id)
        book("heidi", "Rock Night", 1)
