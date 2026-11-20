"""Create demo accounts and machines so the app can be tried (and graded) right away.

Usage:  python manage.py seed_demo
Safe to run more than once.
"""
from django.core.management.base import BaseCommand

from accounts.models import Cooperative, User
from machinery.models import Machine

PASSWORD = "AniDemo#2026"


class Command(BaseCommand):
    help = "Create demo cooperative, admin, farmers and machinery."

    def handle(self, *args, **options):
        coop, _ = Cooperative.objects.get_or_create(
            name="Demo Farmers Cooperative", defaults={"location": "Cebu, Philippines"}
        )
        admin = self._user("demo_admin", "Dana", "Admin", User.Role.ADMIN, coop, "09170000001")
        self._user("demo_farmer1", "Fidel", "Farmer", User.Role.FARMER, coop, "09170000002")
        self._user("demo_farmer2", "Flora", "Farmer", User.Role.FARMER, coop, "09170000003")

        machines = [
            ("Kubota L5018 Tractor", Machine.MachineType.TRACTOR, "50 HP 4WD tractor.", "450.00"),
            ("Combine Harvester", Machine.MachineType.HARVESTER, "Rice combine harvester.", "900.00"),
            ("Rice Thresher", Machine.MachineType.THRESHER, "Portable thresher.", "150.00"),
            ("Water Pump 4in", Machine.MachineType.PUMP, "Diesel irrigation pump.", "0.00"),
        ]
        for name, kind, desc, rate in machines:
            Machine.objects.get_or_create(
                cooperative=coop,
                name=name,
                defaults={"machine_type": kind, "description": desc, "hourly_rate": rate,
                          "created_by": admin},
            )
        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready. Join code: {coop.join_code} | password for all demo users: {PASSWORD}"
        ))

    def _user(self, username, first, last, role, coop, phone):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first, "last_name": last, "email": f"{username}@example.com",
                      "role": role, "cooperative": coop, "contact_number": phone},
        )
        if created:
            user.set_password(PASSWORD)
            user.save()
        return user
