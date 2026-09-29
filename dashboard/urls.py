from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("login/", views.StaffLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", views.HomeView.as_view(), name="home"),
    path("vendors/", views.VendorListView.as_view(), name="vendor_list"),
    path("vendors/add/", views.VendorCreateView.as_view(), name="vendor_add"),
    path("vendors/<int:pk>/edit/", views.VendorUpdateView.as_view(), name="vendor_edit"),
    path("events/", views.EventListView.as_view(), name="event_list"),
    path("events/add/", views.EventCreateView.as_view(), name="event_add"),
    path("events/<int:pk>/edit/", views.EventUpdateView.as_view(), name="event_edit"),
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/<int:pk>/", views.UserDetailView.as_view(), name="user_detail"),
]
