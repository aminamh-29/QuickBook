import django_filters

from .models import Event


class EventFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    date_from = django_filters.DateFilter(field_name="start_time", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="start_time", lookup_expr="date__lte")
    available = django_filters.BooleanFilter(
        method="filter_available", label="Only events with free seats"
    )

    class Meta:
        model = Event
        fields = ["vendor", "location"]

    def filter_available(self, queryset, name, value):
        return queryset.filter(available_seats__gt=0) if value else queryset
