

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from .models import Permission, Role, Department
from .permissions import IsSupervisor
from django.shortcuts import get_object_or_404


from .serializers import RegisterSerializer, UserProfileSerializer, CustomTokenObtainPairSerializer, PermissionSerializer, DepartmentSimpleSerializer, UserSimpleSerializer, RoleSerializer

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [IsAuthenticated, IsSupervisor]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "User registered successfully"},
            status=status.HTTP_201_CREATED
        )

class CustomTokenObtainPairView(TokenObtainPairView, generics.GenericAPIView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]

class AuthenticatedUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


class RolePermissionManagerView(APIView):
    permission_classes = [IsAuthenticated, IsSupervisor]

    def get(self, request):
        """List all roles with their permissions + all available permissions."""
        roles = Role.objects.prefetch_related('permissions').all()
        permissions = Permission.objects.all()

        return Response({
            "roles": RoleSerializer(roles, many=True).data,
            "permissions": PermissionSerializer(permissions, many=True).data
        })

    def post(self, request):
        role_id = request.data.get("role_id")
        add_perms = request.data.get("add_permissions", [])
        remove_perms = request.data.get("remove_permissions", [])

        if not role_id:
            return Response({"error": "role_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        role = get_object_or_404(Role, id=role_id)

        if add_perms:
            perms_to_add = Permission.objects.filter(id__in=add_perms)
            role.permissions.add(*perms_to_add)

        if remove_perms:
            perms_to_remove = Permission.objects.filter(id__in=remove_perms)
            role.permissions.remove(*perms_to_remove)

        return Response({
            "message": "Role permissions updated successfully",
            "role": RoleSerializer(role).data
        }, status=status.HTTP_200_OK)
        
        
class RolesDepartmentsSupervisorsView(APIView):
    permission_classes = [IsAuthenticated, IsSupervisor]

    def get(self, request):
        roles = Role.objects.all()
        roles_data = RoleSerializer(roles, many=True).data
        
        for role in roles_data:
            role.pop("permissions", None)

        departments = Department.objects.all()

        users = User.objects.filter(role__name__in=["Supervisor", "BD_supervisor"])

        return Response({
            "roles": roles_data,
            "departments": DepartmentSimpleSerializer(departments, many=True).data,
            "supervisors": UserSimpleSerializer(users, many=True).data
        }, status=status.HTTP_200_OK)