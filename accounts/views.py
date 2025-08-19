

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from .models import Permission, Role, Department
from .permissions import IsAdministrator
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.conf import settings
import requests


from .serializers import RegisterSerializer, UserProfileSerializer, CustomTokenObtainPairSerializer, PermissionSerializer, DepartmentSimpleSerializer, UserSimpleSerializer, RoleSerializer

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [IsAuthenticated, IsAdministrator]

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
    permission_classes = [IsAuthenticated, IsAdministrator]

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
    permission_classes = [IsAuthenticated, IsAdministrator]

    def get(self, request):
        roles = Role.objects.all()
        roles_data = RoleSerializer(roles, many=True).data
        for role in roles_data:
            role.pop("permissions", None)

        departments = Department.objects.all()

        # Case-insensitive role match to avoid exact string mismatch issues
        users = User.objects.filter(
            Q(role__name__iexact="Administrator") |
            Q(role__name__iexact="BD_Supervisor")
        )

        return Response({
            "roles": roles_data,
            "departments": DepartmentSimpleSerializer(departments, many=True).data,
            "supervisors": UserSimpleSerializer(users, many=True).data
        }, status=status.HTTP_200_OK)
        
        
        
        
        
class GoogleCalendarInitView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Create the OAuth URL
        oauth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={settings.GOOGLE_OAUTH2_CLIENT_ID}&"
            f"redirect_uri={settings.GOOGLE_REDIRECT_URI}&"
            f"response_type=code&"
            f"scope=https://www.googleapis.com/auth/calendar%20https://www.googleapis.com/auth/calendar.events&"
            f"access_type=offline&"
            f"prompt=consent&"
            f"state={request.user.id}"  # Store user ID in state for later retrieval
        )
        
        return Response({'authorization_url': oauth_url}, status=status.HTTP_200_OK)

class GoogleCalendarRedirectView(APIView):
    def get(self, request):
        code = request.GET.get('code')
        state = request.GET.get('state')  # This contains the user ID
        
        if not code:
            return Response({'error': 'Authorization code not provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Exchange authorization code for tokens
        data = {
            'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
            'client_secret': settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': settings.GOOGLE_REDIRECT_URI
        }
        
        response = requests.post('https://oauth2.googleapis.com/token', data=data)
        token_data = response.json()
        
        if 'access_token' not in token_data:
            return Response({'error': 'Failed to obtain access token'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user info from Google
        user_info_response = requests.get(
            'https://www.googleapis.com/oauth2/v1/userinfo',
            headers={'Authorization': f'Bearer {token_data["access_token"]}'}
        )
        user_info = user_info_response.json()
        
        # Find the user
        try:
            user = User.objects.get(id=state)
            user.save_google_tokens(
                token_data['access_token'],
                token_data['refresh_token'],
                token_data['expires_in']
            )
            user.google_sub = user_info['id']
            user.save()
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({'message': 'Google Calendar connected successfully'}, status=status.HTTP_200_OK)