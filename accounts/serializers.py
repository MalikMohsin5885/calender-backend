from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from .models import User, Role, Department, Permission, MeetingEligibility

User = get_user_model()
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role_id = serializers.IntegerField(write_only=True)
    # department may be omitted or null when creating a user
    department_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    supervisor_id = serializers.IntegerField(required=False, allow_null=True)

    # One MeetingEligibility object (optional)
    meeting_eligibility = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id", "name", "email", "password",
            "role_id", "department_id", "supervisor_id",
            "meeting_eligibility",
        ]

    def create(self, validated_data):
        role_id = validated_data.pop("role_id")
        department_id = validated_data.pop("department_id", None)
        supervisor_id = validated_data.pop("supervisor_id", None)
        eligibility_data = validated_data.pop("meeting_eligibility", None)
        password = validated_data.pop("password")

        # ----- Role -----
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            raise serializers.ValidationError({"role_id": "Invalid role ID"})

        # ----- Department -----
        # Determine department: allow None (no department) for non-required departments
        department = None
        # If role is BD or BD_Lead, force department to BD
        if role.name.upper() in ("BD", "BD_LEAD"):
            department, _ = Department.objects.get_or_create(name="BD")
        elif department_id:
            try:
                department = Department.objects.get(id=department_id)
                if department.name == "Business Development":
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
            **validated_data,
        )
        user.set_password(password)
        user.save()

        # ----- Create One MeetingEligibility -----
        if eligibility_data:
            department_items = eligibility_data.get("departments", []) or []
            priority = eligibility_data.get("priority")
            can_take_contract = eligibility_data.get("can_take_contract", True)
            can_take_w2 = eligibility_data.get("can_take_w2", True)

            # Accept either list of department IDs (ints) or names (strs). Empty list is allowed.
            dept_ids = []
            if department_items:
                # if items are ints, assume they are IDs
                if all(isinstance(x, int) for x in department_items):
                    dept_ids = list(Department.objects.filter(id__in=department_items).values_list("id", flat=True))
                    if len(dept_ids) != len(department_items):
                        raise serializers.ValidationError({"meeting_eligibility": "One or more departments are invalid."})
                else:
                    # treat as names
                    valid_names = list(Department.objects.filter(name__in=department_items).values_list("name", flat=True))
                    invalid_names = set(department_items) - set(valid_names)
                    if invalid_names:
                        raise serializers.ValidationError({"meeting_eligibility": f"Invalid department names: {list(invalid_names)}"})
                    dept_ids = list(Department.objects.filter(name__in=department_items).values_list("id", flat=True))

            MeetingEligibility.objects.create(
                user=user,
                departments=dept_ids,
                priority=priority,
                can_take_contract=can_take_contract,
                can_take_w2=can_take_w2,
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
    # Readable fields
    role = serializers.CharField(source='role.name', read_only=True)
    department = serializers.CharField(source='department.name', read_only=True)
    supervisor = serializers.CharField(source='supervisor.name', read_only=True)

    # Writable ids for updating relations
    role_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    department_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    supervisor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    meeting_eligibilities = MeetingEligibilitySerializer(many=True)

    class Meta:
        model = User
        fields = [
            'id', 'name', 'email', 'password',
            'role', 'department', 'supervisor',
            'role_id', 'department_id', 'supervisor_id',
            'is_active', 'meeting_eligibilities'
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}
        }

    def update(self, instance, validated_data):
        eligibilities_data = validated_data.pop('meeting_eligibilities', None)

        # Handle relational ids explicitly
        role_id = validated_data.pop('role_id', None)
        department_id = validated_data.pop('department_id', None)
        supervisor_id = validated_data.pop('supervisor_id', None)

        if role_id is not None:
            try:
                instance.role = Role.objects.get(id=role_id)
            except Role.DoesNotExist:
                raise serializers.ValidationError({"role_id": "Invalid role ID"})

        if department_id is not None:
            # If role was changed to BD or BD_Lead, force department to BD
            if instance.role and instance.role.name.upper() in ("BD", "BD_LEAD"):
                instance.department, _ = Department.objects.get_or_create(name="BD")
            else:
                if department_id == None:
                    instance.department = None
                else:
                    try:
                        instance.department = Department.objects.get(id=department_id)
                    except Department.DoesNotExist:
                        raise serializers.ValidationError({"department_id": "Invalid department ID"})

        if supervisor_id is not None:
            if supervisor_id == None:
                instance.supervisor = None
            else:
                try:
                    instance.supervisor = User.objects.get(id=supervisor_id)
                except User.DoesNotExist:
                    raise serializers.ValidationError({"supervisor_id": "Invalid supervisor ID"})

        # Update other simple fields
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