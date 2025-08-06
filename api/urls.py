from django.urls import path
from .views import MeetingListCreateView, DepartmentAndUsersView, MeetingUpdateView,UserListCreateUpdateView

urlpatterns = [
    path("meetings/", MeetingListCreateView.as_view(), name="meeting-list"),
    path("meetings/<int:pk>/edit", MeetingUpdateView.as_view(), name="meeting-update"),
    path("departments-users/", DepartmentAndUsersView.as_view(), name="departments-users"),
    
    path('users/', UserListCreateUpdateView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserListCreateUpdateView.as_view(), name='user-update'),
]
