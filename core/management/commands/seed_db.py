from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Role, Permission, Department

User = get_user_model()


class Command(BaseCommand):
    help = "Seed roles, permissions, departments, and a default user"

    def handle(self, *args, **kwargs):
        self.seed_permissions_and_roles()
        self.seed_departments()
        self.seed_default_user()

    def seed_permissions_and_roles(self):
        self.stdout.write("Seeding permissions and roles...")

        perms = [
            "meeting.schedule_meeting",
            "meeting.view_all_meetings",
            "meeting.view_own_meetings",
            "meeting.view_assigned_meetings",
            "meeting.delete_meeting",
            "meeting.update_all_meetings",
            "meeting.update_own_meetings",
        ]

        for codename in perms:
            Permission.objects.get_or_create(name=codename)

        roles_map = {
            "Supervisor": perms,
            "BD": [
                "meeting.schedule_meeting",
                "meeting.view_own_meetings",
                "meeting.update_own_meetings",
            ],
            "Closer": ["meeting.view_assigned_meetings"],
        }

        for role_name, role_perms in roles_map.items():
            role, _ = Role.objects.get_or_create(name=role_name)
            for codename in role_perms:
                perm = Permission.objects.get(name=codename)
                role.permissions.add(perm)

        self.stdout.write(self.style.SUCCESS("Roles and permissions seeded."))

    def seed_departments(self):
        self.stdout.write("Seeding departments...")

        departments = [
            "Machine Learning",
            "Data Engineering",
            "Artificial Intelligence",
            "Dev",
            "BD",
        ]

        for dept_name in departments:
            Department.objects.get_or_create(name=dept_name)

        self.stdout.write(self.style.SUCCESS("Departments seeded."))

    def seed_default_user(self):
        self.stdout.write("Seeding default user...")

        email = "mohsin@gmail.com"
        name = "Mohsin"
        password = "test@123"

        try:
            supervisor_role = Role.objects.get(name="Supervisor")
            ml_department = Department.objects.get(name="Machine Learning")
        except (Role.DoesNotExist, Department.DoesNotExist) as e:
            self.stdout.write(self.style.ERROR(f"Missing required role/department: {e}"))
            return

        if not User.objects.filter(email=email).exists():
            User.objects.create_user(
                email=email,
                name=name,
                password=password,
                role=supervisor_role,
                department=ml_department,
            )
            self.stdout.write(self.style.SUCCESS("Default user 'Mohsin' created."))
        else:
            self.stdout.write(self.style.WARNING("User already exists."))
