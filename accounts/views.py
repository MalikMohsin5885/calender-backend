

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from .models import Permission, Role, Department
from .permissions import IsChief
from django.shortcuts import get_object_or_404
from django.db.models import Q
# from django.views.decorators.csrf import csrf_exempt
# from django.utils.decorators import method_decorator
import requests
from .utils import extract_google_user_info 
import jwt  # PyJWT



from .serializers import RegisterSerializer, UserProfileSerializer, CustomTokenObtainPairSerializer, PermissionSerializer, DepartmentSimpleSerializer, UserSimpleSerializer, RoleSerializer

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [IsAuthenticated, IsChief]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "User registered successfully"},
            status=status.HTTP_201_CREATED)

class CustomTokenObtainPairView(TokenObtainPairView, generics.GenericAPIView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]

class AuthenticatedUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


class RolePermissionManagerView(APIView):
    permission_classes = [IsAuthenticated, IsChief]

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
    permission_classes = [IsAuthenticated, IsChief]

    def get(self, request):
        roles = Role.objects.all()
        roles_data = RoleSerializer(roles, many=True).data
        for role in roles_data:
            role.pop("permissions", None)   

        departments = Department.objects.all()

        # Case-insensitive role match to avoid exact string mismatch issues
        users = User.objects.filter(
            Q(role__name__iexact="Chief") |
            Q(role__name__iexact="BD_Supervisor")
        )

        return Response({
            "roles": roles_data,
            "departments": DepartmentSimpleSerializer(departments, many=True).data,
            "supervisors": UserSimpleSerializer(users, many=True).data
        }, status=status.HTTP_200_OK)

class GoogleAuthCodeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        authorization_code = request.data.get("code")
        
        if not authorization_code:
            return Response({"error": "code is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Google OAuth details (from your GCP JSON)
        client_id = "34902771404-95o6rsaurj49agpr5mihlqthi0d67v7u.apps.googleusercontent.com"
        client_secret = "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"
        redirect_uri = "http://localhost:8000/auth/google/callback/"  # must match GCP

        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": authorization_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": "postmessage",
            # "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            r = requests.post(token_url, data=data)
            token_response = r.json()
            if "error" in token_response:
                return Response({"error": token_response}, status=status.HTTP_400_BAD_REQUEST)

            id_token = token_response.get('id_token') 
            
            if not id_token: 
                return Response({"error": "Missing id_token in token response"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Decode the id_token (verify signature with Google's public keys in production)
            decoded_token = jwt.decode(id_token, options={"verify_signature": False})
            google_email = decoded_token.get("email")
                
            if not google_email:
                return Response({"error": "Google account email not found"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if Google email matches the logged-in user email
            if request.user.email.lower() != google_email.lower():
                return Response(
                    {"error": "You must connect with the same email you used to log in."},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            user = request.user 
            print("Logged-in user:", user.email)
            print("Google email from token:", google_email)
                
            
            # Save Google tokens and mark as linked 
            user.save_google_tokens( access_token=token_response.get('access_token'), refresh_token=token_response.get('refresh_token'), expires_in=token_response.get('expires_in', 3600),token_id = token_response.get('id_token')  )

            return Response({
                "message": "Tokens received",
                "tokens": token_response
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
class GoogleLinkedStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({"google_linked": user.google_linked})

