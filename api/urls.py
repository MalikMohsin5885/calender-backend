from django.urls import path
from .views import MeetingListCreateView, UsersListView, MeetingUpdateView

urlpatterns = [
    path("meetings/", MeetingListCreateView.as_view(), name="meeting-list"),
    path("meetings/<int:pk>/", MeetingUpdateView.as_view(), name="meeting-update"),
    path("users/", UsersListView.as_view(), name="users-list"),  # optional
]
