

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from .models import Permission, Role
from .permissions import IsSupervisor

from .serializers import RegisterSerializer, UserProfileSerializer, CustomTokenObtainPairSerializer

User = get_user_model()

class RegisterView(generics.ListCreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [IsAuthenticated, IsSupervisor]

    def create(self, request, *args, **kwargs):
        # (you can keep your custom message here)
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
    
    
# add the sedder permsion for supervisor only  
class SeedRolesPermissionsView(APIView):
    # permission_classes = [IsAdminUser]

    def get(self, request):
        perms = [
            "meeting.schedule_meeting",
            "meeting.view_all_meetings",
            "meeting.view_own_meetings",
            "meeting.view_assigned_meetings",
            "meeting.delete_meeting",
        ]
        for codename in perms:
            Permission.objects.get_or_create(name=codename)

        roles_map = {
            "Supervisor": perms,
            "BD": ["meeting.schedule_meeting", "meeting.view_own_meetings"],
            "Member": ["meeting.view_assigned_meetings"],
        }
        for role_name, role_perms in roles_map.items():
            role, _ = Role.objects.get_or_create(name=role_name)
            for codename in role_perms:
                perm = Permission.objects.get(name=codename)
                role.permissions.add(perm)

        return Response({"status": "seeded"}, status=200)
    

