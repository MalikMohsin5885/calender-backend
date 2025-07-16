from rest_framework.permissions import BasePermission

class IsSupervisor(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user.role, "name", "").lower() == "supervisor"
        )

class IsSupervisorOrBD(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        role_name = getattr(request.user.role, "name", "").lower()
        return role_name in ["supervisor", "bd"]

