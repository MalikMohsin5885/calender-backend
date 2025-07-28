from django.urls import path
from .views import MeetingListCreateView, DepartmentAndUsersView, MeetingUpdateView

urlpatterns = [
    path("meetings/", MeetingListCreateView.as_view(), name="meeting-list"),
    path("meetings/<int:pk>/", MeetingUpdateView.as_view(), name="meeting-update"),
    path("departments-users/", DepartmentAndUsersView.as_view(), name="departments-users"),

]
