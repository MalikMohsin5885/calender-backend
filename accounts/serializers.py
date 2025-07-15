from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from .models import User, Role 

User = get_user_model()

# class RegisterSerializer(serializers.ModelSerializer):
#     password = serializers.CharField(write_only=True, min_length=6)

#     class Meta:
#         model = User
#         fields = ['id', 'name', 'email', 'password']

#     def create(self, validated_data):
#         password = validated_data.pop('password', None)
#         user = User.objects.create(**validated_data)
#         if password:
#             user.set_password(password)
#         user.is_verified = False
#         user.save()
#         return user
    

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'password', 'role']

    def create(self, validated_data):
        role_name = validated_data.pop('role', None)
        password = validated_data.pop('password', None)

        # 🔽 Lowercase the email
        validated_data['email'] = validated_data['email'].lower()

        try:
            role = Role.objects.get(name__iexact=role_name)
        except Role.DoesNotExist:
            raise serializers.ValidationError({"role": "Invalid role"})

        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.role = role
        user.save()
        return user



class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        email = attrs.get('email', '').lower()  # 🔽 lowercased email
        password = attrs.get('password', '')

        # Use 'username' as key if USERNAME_FIELD = 'email'
        user = authenticate(
            request=self.context.get('request'),
            username=email,
            password=password
        )
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")

        refresh = self.get_token(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["name"] = user.name
        token["email"] = user.email
        return token


class UserProfileSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='role.name', read_only=True)
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'role']