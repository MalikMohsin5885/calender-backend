from django.urls import path
from .views import MeetingListCreateView

urlpatterns = [
    path('meetings/', MeetingListCreateView.as_view(), name='meeting-list-create'),
]
