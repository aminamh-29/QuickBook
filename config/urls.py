"""Root URL configuration."""
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("", RedirectView.as_view(url="/dashboard/", permanent=False)),
    # REST API
    path("api/auth/", include("accounts.urls")),
    path("api/referrals/", include("referrals.urls")),
    path("api/", include("events.urls")),
    path("api/", include("bookings.urls")),
    # OpenAPI / Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # Staff dashboard
    path("dashboard/", include("dashboard.urls")),
]
