from django.urls import path
from .views import MeetingListCreateView, DepartmentAndUsersView, MeetingUpdateView,UserListCreateUpdateView, MeetingRemarksUpdateView
from accounts.views import RolePermissionManagerView, RolesDepartmentsSupervisorsView
urlpatterns = [
    path("meetings/", MeetingListCreateView.as_view(), name="meeting-list"),
    path("meetings/<int:pk>/edit", MeetingUpdateView.as_view(), name="meeting-update"),
    path("meetings/<int:pk>/remarks/", MeetingRemarksUpdateView.as_view(), name="update-meeting-remarks"),
    path("departments-users/", DepartmentAndUsersView.as_view(), name="departments-users"),
    
    path('users/', UserListCreateUpdateView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserListCreateUpdateView.as_view(), name='user-update'),
    path('roles-permissions/', RolePermissionManagerView.as_view(), name='roles-permissions'),
    path("roles-departments-supervisors/", RolesDepartmentsSupervisorsView.as_view(), name="roles-departments-supervisors"),
]
