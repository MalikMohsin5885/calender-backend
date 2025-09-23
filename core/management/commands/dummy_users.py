from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Role, Department, MeetingEligibility

User = get_user_model()


class Command(BaseCommand):
    help = "Seed complex meeting data with BD, BD Leads, Closer Leads, and Closers (chief must exist)"

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding complex meeting test data...")

        # === Roles ===
        bd_role, _ = Role.objects.get_or_create(name="BD")
        bd_lead_role, _ = Role.objects.get_or_create(name="BD_Lead")
        closer_role, _ = Role.objects.get_or_create(name="Closer")
        closer_lead_role, _ = Role.objects.get_or_create(name="Closer_Lead")

        # === Departments ===
        bd_dept, _ = Department.objects.get_or_create(name="BD")
        data_engg_dept, _ = Department.objects.get_or_create(name="Data Engineering")
        ai_dept, _ = Department.objects.get_or_create(name="Artificial Intelligence")

        # === Chief (must exist already) ===
        try:
            chief = User.objects.get(email="malikmohsin8239@gmail.com")
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR("Chief user not found. Please create malikmohsin8239@gmail.com first.")
            )
            return

        def get_or_create_user(email, name, role, dept, supervisor, password="test@123"):
            """Helper to create user with hashed password if not exists"""
            user = User.objects.filter(email=email).first()
            if not user:
                user = User.objects.create_user(
                    email=email,
                    name=name,
                    password=password,
                    role=role,
                    department=dept,
                    supervisor=supervisor,
                )
                self.stdout.write(self.style.SUCCESS(f"Created user {email}"))
            return user

        

        # === BD Leads (different emails, not clashing with BD user) ===
        bd_lead1 = get_or_create_user(
            "muhammadmohsin@gmail.com", "BD Lead 1", bd_lead_role, bd_dept, chief
        )
        bd_lead2 = get_or_create_user(
            "bdlead2@example.com", "BD Lead 2", bd_lead_role, bd_dept, chief
        )
        
        # === BD User (plain BD, not lead) ===
        bd_user = get_or_create_user(
            "m.adam@alphabridgeconsulting.com",
            "BD User",
            bd_role,
            bd_dept,
            bd_lead1,
        )

        # === Closer Leads ===
        closer_lead1 = get_or_create_user(
            "mohsin.rasheed@alphabridgeconsulting.com",
            "Closer Lead DataEngg",
            closer_lead_role,
            data_engg_dept,
            chief,
        )
        closer_lead2 = get_or_create_user(
            "closerlead2@example.com",
            "Closer Lead AI",
            closer_lead_role,
            ai_dept,
            chief,
        )

        # === Closers ===
        closer1 = get_or_create_user(
            "fazeel.khalid@alphabridgeconsulting.com",
            "Closer 1",
            closer_role,
            data_engg_dept,
            closer_lead1,
        )
        closer2 = get_or_create_user(
            "ali.ijaz@alphabridgeconsulting.com",
            "Closer 2",
            closer_role,
            data_engg_dept,
            closer_lead1,
        )
        closer3 = get_or_create_user(
            "closer3@example.com",
            "Closer 3",
            closer_role,
            data_engg_dept,
            closer_lead1,
        )
        closer4 = get_or_create_user(
            "closer4@example.com",
            "Closer 4",
            closer_role,
            data_engg_dept,
            closer_lead1,
        )
        closer5 = get_or_create_user(
            "closer5@example.com",
            "Closer 5",
            closer_role,
            ai_dept,
            closer_lead2,
        )
        closer6 = get_or_create_user(
            "closer6@example.com",
            "Closer 6",
            closer_role,
            ai_dept,
            closer_lead2,
        )

        # === Meeting Eligibility (no BD dept) ===
        MeetingEligibility.objects.get_or_create(
            user=closer1,
            defaults={
                "departments": [data_engg_dept.id],
                "priority": 4,
                "can_take_contract": True,
                "can_take_w2": False,
            },
        )
        MeetingEligibility.objects.get_or_create(
            user=closer2,
            defaults={
                "departments": [data_engg_dept.id, ai_dept.id],
                "priority": 4,
                "can_take_contract": False,
                "can_take_w2": True,
            },
        )
        MeetingEligibility.objects.get_or_create(
            user=closer3,
            defaults={
                "departments": [data_engg_dept.id],
                "priority": 1,
                "can_take_contract": True,
                "can_take_w2": True,
            },
        )
        MeetingEligibility.objects.get_or_create(
            user=closer4,
            defaults={
                "departments": [data_engg_dept.id, ai_dept.id],
                "priority": 2,
                "can_take_contract": False,
                "can_take_w2": True,
            },
        )
        MeetingEligibility.objects.get_or_create(
            user=closer5,
            defaults={
                "departments": [ai_dept.id],
                "priority": 1,
                "can_take_contract": True,
                "can_take_w2": False,
            },
        )
        MeetingEligibility.objects.get_or_create(
            user=closer6,
            defaults={
                "departments": [ai_dept.id, data_engg_dept.id],
                "priority": 5,
                "can_take_contract": False,
                "can_take_w2": True,
            },
        )

        self.stdout.write(
            self.style.SUCCESS("Complex meeting data seeded successfully with BD role, leads, and hashed passwords")
        )
