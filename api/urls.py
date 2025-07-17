from django.urls import path
from .views import MeetingListCreateView, UsersListView, MeetingUpdateView

urlpatterns = [
    path('meetings/', MeetingListCreateView.as_view(), name='meeting-list-create'),
    path('meetings/<int:pk>/edit/', MeetingUpdateView.as_view(), name='meeting-edit'),
    path('users/', UsersListView.as_view(), name='users-list'),
]
