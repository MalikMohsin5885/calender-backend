from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from .models import User, Role, Department, Permission, MeetingEligibility

User = get_user_model()
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role_id = serializers.IntegerField(write_only=True)
    department_id = serializers.IntegerField(write_only=True)
    supervisor_id = serializers.IntegerField(required=False, allow_null=True)

    # MeetingEligibility fields
    departments = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of Department IDs this user is eligible for"
    )
    priority = serializers.IntegerField(required=False, allow_null=True)
    can_take_contract = serializers.BooleanField(default=True)
    can_take_w2 = serializers.BooleanField(default=True)

    class Meta:
        model = User
        fields = [
            'id', 'name', 'email', 'password',
            'role_id', 'department_id', 'supervisor_id',
            # eligibility
            'departments', 'priority', 'can_take_contract', 'can_take_w2'
        ]

    def create(self, validated_data):
        role_id = validated_data.pop('role_id')
        department_id = validated_data.pop('department_id')
        supervisor_id = validated_data.pop('supervisor_id', None)

        # eligibility fields
        departments = validated_data.pop('departments', [])
        priority = validated_data.pop('priority', None)
        can_take_contract = validated_data.pop('can_take_contract', True)
        can_take_w2 = validated_data.pop('can_take_w2', True)

        password = validated_data.pop('password')

        # ----- Role -----
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            raise serializers.ValidationError({"role_id": "Invalid role ID"})

        # ----- Department -----
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

        # ----- Supervisor -----
        supervisor = None
        if supervisor_id:
            try:
                supervisor = User.objects.get(id=supervisor_id)
            except User.DoesNotExist:
                raise serializers.ValidationError({"supervisor_id": "Invalid supervisor ID"})

        # ----- Create User -----
        user = User(
            role=role,
            department=department,
            supervisor=supervisor,
            **validated_data
        )
        user.set_password(password)
        user.save()

        # ----- Create MeetingEligibility -----
        if departments:
            MeetingEligibility.objects.create(
                user=user,
                departments=departments,
                priority=priority,
                can_take_contract=can_take_contract,
                can_take_w2=can_take_w2
            )

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
    department = serializers.CharField(source='department.name', read_only=True)
    supervisor = serializers.CharField(source='supervisor.name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'role', 'department', 'supervisor', 'is_active']

class DepartmentSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name']


class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email']

class MeetingEligibilitySerializer(serializers.ModelSerializer):
    departments = serializers.ListField(
        child=serializers.CharField(),  # Accept list of department names
    )

    class Meta:
        model = MeetingEligibility
        fields = ['id', 'departments', 'can_take_contract', 'can_take_w2', 'priority']
        extra_kwargs = {
            'id': {'read_only': True}
        }

    def to_representation(self, instance):
        # Convert department IDs → department names
        representation = super().to_representation(instance)
        from accounts.models import Department  # adjust import if needed
        department_names = list(
            Department.objects.filter(id__in=instance.departments).values_list("name", flat=True)
        )
        representation['departments'] = department_names
        return representation

    def to_internal_value(self, data):
        # Convert department names → IDs
        from accounts.models import Department
        departments = data.get("departments", [])
        if departments:
            department_ids = list(
                Department.objects.filter(name__in=departments).values_list("id", flat=True)
            )
            if len(department_ids) != len(departments):
                raise serializers.ValidationError({"departments": "One or more departments are invalid."})
            data["departments"] = department_ids
        return super().to_internal_value(data)


class UserListUpdateSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='role.name', read_only=True)
    department = serializers.CharField(source='department.name', read_only=True)
    supervisor = serializers.CharField(source='supervisor.name', read_only=True)

    meeting_eligibilities = MeetingEligibilitySerializer(many=True)

    class Meta:
        model = User
        fields = [
            'id', 'name', 'email', 'password',
            'role', 'department', 'supervisor',
            'is_active', 'meeting_eligibilities'
        ]
        read_only_fields = ['id', 'role', 'department', 'supervisor']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}
        }

    def update(self, instance, validated_data):
        eligibilities_data = validated_data.pop('meeting_eligibilities', None)

        # Update user fields
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()

        # Update MeetingEligibilities
        if eligibilities_data is not None:
            instance.meeting_eligibilities.all().delete()
            for eligibility in eligibilities_data:
                MeetingEligibility.objects.create(user=instance, **eligibility)

        return instance


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name']

class RoleSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True)

    class Meta:
        model = Role
        fields = ['id', 'name', 'permissions']