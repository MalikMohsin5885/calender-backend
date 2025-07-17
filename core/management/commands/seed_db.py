from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Role, Permission
User = get_user_model()

class Command(BaseCommand):
    help = "Seed roles, permissions, and a default user"

    def handle(self, *args, **kwargs):
        self.seed_permissions_and_roles()
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
            "Member": ["meeting.view_assigned_meetings"],
        }

        for role_name, role_perms in roles_map.items():
            role, _ = Role.objects.get_or_create(name=role_name)
            for codename in role_perms:
                perm = Permission.objects.get(name=codename)
                role.permissions.add(perm)

        self.stdout.write(self.style.SUCCESS("Roles and permissions seeded."))

    def seed_default_user(self):
        self.stdout.write("Seeding default user...")

        email = "malikmohsin8239@gmail.com"
        name = "malik mohsin"
        password = "test@123"

        supervisor_role = Role.objects.get(name="Supervisor")

        if not User.objects.filter(email=email).exists():
            User.objects.create_user(
                email=email,
                name=name,
                password=password,
                role=supervisor_role
            )
            self.stdout.write(self.style.SUCCESS("Default user 'malik mohsin' created."))
        else:
            self.stdout.write(self.style.WARNING("User already exists."))
