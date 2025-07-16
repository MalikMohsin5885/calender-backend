from django.urls import path
from .views import MeetingListCreateView, UsersListView

urlpatterns = [
    path('meetings/', MeetingListCreateView.as_view(), name='meeting-list-create'),
    path('users/', UsersListView.as_view(), name='users-list'),
]
