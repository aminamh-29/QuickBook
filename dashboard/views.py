"""Staff dashboard views. Thin: querying and rendering only."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from bookings.models import Booking
from events.models import Event, Vendor
from referrals import services as referral_services

from .forms import EventForm, StaffAuthenticationForm, VendorForm

User = get_user_model()
PAGE_SIZE = 10


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Anonymous users are redirected to login; non-staff users get a 403."""

    def test_func(self):
        user = self.request.user
        return user.is_active and user.is_staff


class StaffLoginView(LoginView):
    template_name = "dashboard/login.html"
    authentication_form = StaffAuthenticationForm
    redirect_authenticated_user = False


class HomeView(StaffRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stats"] = [
            ("Total Customers", User.objects.filter(is_staff=False).count(), "people"),
            ("Total Vendors", Vendor.objects.count(), "shop"),
            ("Total Events", Event.objects.count(), "calendar-event"),
            ("Total Bookings", Booking.objects.count(), "ticket-perforated"),
        ]
        return ctx


class SearchListMixin:
    """Pagination plus a ``q`` search box; subclasses set ``search_fields``."""

    paginate_by = PAGE_SIZE
    search_fields = ()

    def apply_search(self, queryset):
        q = self.request.GET.get("q", "").strip()
        if q:
            cond = Q()
            for field in self.search_fields:
                cond |= Q(**{f"{field}__icontains": q})
            queryset = queryset.filter(cond)
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()  # keeps filters across pages
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


# Vendors -------------------------------------------------------------------

class VendorListView(StaffRequiredMixin, SearchListMixin, ListView):
    model = Vendor
    template_name = "dashboard/vendor_list.html"
    context_object_name = "vendors"
    search_fields = ("name", "contact_email", "phone")

    def get_queryset(self):
        qs = self.apply_search(
            Vendor.objects.annotate(event_count=Count("events")).order_by("name")
        )
        status = self.request.GET.get("status")
        if status in ("active", "inactive"):
            qs = qs.filter(is_active=status == "active")
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status"] = self.request.GET.get("status", "")
        return ctx


class VendorCreateView(StaffRequiredMixin, CreateView):
    model = Vendor
    form_class = VendorForm
    template_name = "dashboard/form.html"
    success_url = reverse_lazy("dashboard:vendor_list")
    extra_context = {"title": "Add Vendor", "back_url": reverse_lazy("dashboard:vendor_list")}

    def form_valid(self, form):
        messages.success(self.request, "Vendor created.")
        return super().form_valid(form)


class VendorUpdateView(StaffRequiredMixin, UpdateView):
    model = Vendor
    form_class = VendorForm
    template_name = "dashboard/form.html"
    success_url = reverse_lazy("dashboard:vendor_list")
    extra_context = {"title": "Update Vendor", "back_url": reverse_lazy("dashboard:vendor_list")}

    def form_valid(self, form):
        messages.success(self.request, "Vendor updated.")
        return super().form_valid(form)


# Events --------------------------------------------------------------------

class EventListView(StaffRequiredMixin, SearchListMixin, ListView):
    model = Event
    template_name = "dashboard/event_list.html"
    context_object_name = "events"
    search_fields = ("title", "location", "vendor__name")

    def get_queryset(self):
        qs = self.apply_search(Event.objects.select_related("vendor")).order_by("-start_time")
        params = self.request.GET
        if params.get("vendor", "").isdigit():
            qs = qs.filter(vendor_id=params["vendor"])
        status = params.get("status")
        now = timezone.now()
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        elif status == "upcoming":
            qs = qs.filter(start_time__gt=now)
        elif status == "past":
            qs = qs.filter(start_time__lte=now)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["vendors"] = Vendor.objects.all()
        ctx["vendor_id"] = self.request.GET.get("vendor", "")
        ctx["status"] = self.request.GET.get("status", "")
        return ctx


class EventCreateView(StaffRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = "dashboard/form.html"
    success_url = reverse_lazy("dashboard:event_list")
    extra_context = {"title": "Add Event", "back_url": reverse_lazy("dashboard:event_list")}

    def form_valid(self, form):
        messages.success(self.request, "Event created.")
        return super().form_valid(form)


class EventUpdateView(StaffRequiredMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = "dashboard/form.html"
    success_url = reverse_lazy("dashboard:event_list")
    extra_context = {"title": "Update Event", "back_url": reverse_lazy("dashboard:event_list")}

    def form_valid(self, form):
        messages.success(self.request, "Event updated.")
        return super().form_valid(form)


# Users ---------------------------------------------------------------------

class UserListView(StaffRequiredMixin, SearchListMixin, ListView):
    model = User
    template_name = "dashboard/user_list.html"
    context_object_name = "users"
    search_fields = ("username", "email", "phone", "referral_code")

    def get_queryset(self):
        qs = self.apply_search(User.objects.filter(is_staff=False)).order_by("-date_joined")
        return qs.annotate(booking_count=Count("bookings"))


class UserDetailView(StaffRequiredMixin, DetailView):
    model = User
    template_name = "dashboard/user_detail.html"
    context_object_name = "customer"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.object
        q = self.request.GET.get("q", "").strip()
        try:
            depth = min(max(int(self.request.GET.get("depth", 3)), 1), 6)
        except ValueError:
            depth = 3

        ctx["bookings"] = user.bookings.select_related("event")[:10]
        ctx["stats"] = referral_services.get_stats(user)
        ctx["root"] = referral_services.get_root(user)
        ctx["tree"] = referral_services.build_tree(user, depth)
        ctx["depth"] = depth
        ctx["depth_options"] = range(1, 7)
        ctx["q"] = q
        if q:
            ql = q.lower()
            ctx["matches"] = [
                (u, d)
                for u, d in referral_services.get_descendants(user)
                if ql in u.username.lower()
                or ql in u.email.lower()
                or ql in u.referral_code.lower()
            ]
        return ctx
