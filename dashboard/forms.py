from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.db.models import F

from events.models import Event, Vendor


class StaffAuthenticationForm(AuthenticationForm):
    """Login form that only lets active staff users in."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(
                "This account does not have staff access.", code="not_staff"
            )


class BootstrapFormMixin:
    """Add Bootstrap classes to all widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            css = "form-check-input" if isinstance(widget, forms.CheckboxInput) else "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


class VendorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ["name", "contact_email", "phone", "address", "is_active"]
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}


class EventForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "vendor", "title", "description", "location", "start_time",
            "price", "total_seats", "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "start_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_time"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]
        self.fields["vendor"].queryset = Vendor.objects.filter(is_active=True) | (
            Vendor.objects.filter(pk=self.instance.vendor_id)
            if self.instance.pk
            else Vendor.objects.none()
        )

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price

    def clean_total_seats(self):
        total = self.cleaned_data["total_seats"]
        if self.instance.pk:
            booked = self.instance.total_seats - self.instance.available_seats
            if total < booked:
                raise forms.ValidationError(
                    f"{booked} seat(s) are already booked; total cannot be lower."
                )
        return total

    def save(self, commit=True):
        event = super().save(commit=False)
        if not event.pk:
            event.available_seats = event.total_seats
            if commit:
                event.save()
            return event

        # Update: never overwrite available_seats with a stale value, since a
        # customer may book while staff edit. Apply the change as a delta.
        with transaction.atomic():
            old_total = (
                Event.objects.select_for_update().get(pk=event.pk).total_seats
            )
            event.save(update_fields=list(self.Meta.fields))
            delta = event.total_seats - old_total
            if delta:
                Event.objects.filter(pk=event.pk).update(
                    available_seats=F("available_seats") + delta
                )
                event.refresh_from_db(fields=["available_seats"])
        return event
