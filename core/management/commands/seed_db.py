import random
from django.core.management.base import BaseCommand
from faker import Faker
from accounts.models import Company, User
from api.models import Role, Permission, UserRoles, RolePermissions

fake = Faker()

class Command(BaseCommand):
    help = "Populate the database with random HRMS-related data"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Seeding data..."))

        # Create Companies
        companies = []
        for _ in range(5):  # Creating 5 companies
            company = Company.objects.create(
                name=fake.company(),
                industry=fake.job(),
                location=fake.city(),
                email=fake.company_email(),
                phone=fake.phone_number()
            )
            companies.append(company)

        self.stdout.write(self.style.SUCCESS(f"Created {len(companies)} companies"))

        # Create Users
        users = []
        for _ in range(20):  # Creating 20 users
            user = User.objects.create_user(
                email=fake.email(),
                fname=fake.first_name(),
                lname=fake.last_name(),
                phone=fake.phone_number(),
                password="password123",
                company=random.choice(companies)
            )
            users.append(user)

        self.stdout.write(self.style.SUCCESS(f"Created {len(users)} users"))

        # Create Roles
        roles = []
        role_names = ["HR Manager", "Recruiter", "Employee", "HR Admin"]
        for role_name in role_names:
            role = Role.objects.create(
                name=role_name,
                description=fake.text()
            )
            roles.append(role)

        self.stdout.write(self.style.SUCCESS(f"Created {len(roles)} roles"))

        # Create Permissions
        permissions = []
        permission_names = ["View Dashboard", "Manage Employees", "Approve Leaves", "Edit Payroll"]
        for perm_name in permission_names:
            permission = Permission.objects.create(
                name=perm_name,
                description=fake.text()
            )
            permissions.append(permission)

        self.stdout.write(self.style.SUCCESS(f"Created {len(permissions)} permissions"))

        # Assign Roles to Users
        for user in users:
            role = random.choice(roles)
            UserRoles.objects.create(user=user, role=role)

        self.stdout.write(self.style.SUCCESS("Assigned roles to users"))

        # Assign Permissions to Roles
        for role in roles:
            assigned_perms = random.sample(permissions, k=2)  # Assign 2 random permissions per role
            for permission in assigned_perms:
                RolePermissions.objects.get_or_create(role=role, permission=permission)

        self.stdout.write(self.style.SUCCESS("Assigned permissions to roles"))
        self.stdout.write(self.style.SUCCESS("Seeding completed successfully!"))
