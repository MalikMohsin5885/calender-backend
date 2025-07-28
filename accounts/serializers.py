from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from .models import User, Role, Department 

User = get_user_model()
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role_id = serializers.IntegerField(write_only=True)
    department_id = serializers.IntegerField(write_only=True)
    supervisor_id = serializers.IntegerField(required=False, allow_null=True)
    priority = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'password', 'role_id', 'department_id', 'supervisor_id', 'priority']

    def create(self, validated_data):
        role_id = validated_data.pop('role_id')
        department_id = validated_data.pop('department_id')
        supervisor_id = validated_data.pop('supervisor_id', None)
        password = validated_data.pop('password')

        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            raise serializers.ValidationError({"role_id": "Invalid role ID"})
        
        try:
            if role.name == 'BD':
                department, _ = Department.objects.get_or_create(name='BD')
            else:
                department = Department.objects.get(id=department_id)
                if department.name == 'Business Development':
                    raise serializers.ValidationError(
                        {"department_id": "Only BD role can have the Business Development department"}
                    )
        except Department.DoesNotExist:
            raise serializers.ValidationError({"department_id": "Invalid department ID"})


        supervisor = None
        if supervisor_id is not None:
            try:
                supervisor = User.objects.get(id=supervisor_id)
            except User.DoesNotExist:
                raise serializers.ValidationError({"supervisor_id": "Invalid supervisor ID"})

        user = User(
            role=role,
            department=department,
            supervisor=supervisor,
            **validated_data
        )
        user.set_password(password)
        user.save()
        return user



class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        email = attrs.get('email', '').lower()
        password = attrs.get('password', '')

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

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name']