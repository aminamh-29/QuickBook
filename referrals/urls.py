from django.urls import path

from . import views

app_name = "referrals"

urlpatterns = [
    path("<int:user_id>/tree/", views.TreeView.as_view(), name="tree"),
    path("<int:user_id>/root/", views.RootView.as_view(), name="root"),
    path("<int:user_id>/stats/", views.StatsView.as_view(), name="stats"),
]
