from django.test import TestCase
from django.urls import reverse

from accounts.models import Cooperative, User
from machinery.models import Machine


def make_coop_admin(username="admin1", coop_name="Coop One"):
    coop = Cooperative.objects.create(name=coop_name)
    admin = User.objects.create_user(
        username=username, email=f"{username}@x.com", password="pass12345", role=User.Role.ADMIN,
        cooperative=coop,
    )
    return coop, admin


def make_farmer(coop, username="farmer1"):
    return User.objects.create_user(
        username=username, email=f"{username}@x.com", password="pass12345", role=User.Role.FARMER,
        cooperative=coop,
    )


class MachineManagementTests(TestCase):
    def setUp(self):
        self.coop, self.admin = make_coop_admin()
        self.farmer = make_farmer(self.coop)
        self.payload = {
            "name": "Kubota Tractor", "machine_type": "tractor", "description": "",
            "hourly_rate": "350.00", "status": "available",
        }

    def test_requires_login(self):
        r = self.client.get(reverse("machinery:machine_list"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_farmer_forbidden(self):
        self.client.force_login(self.farmer)
        self.assertEqual(self.client.get(reverse("machinery:machine_list")).status_code, 403)
        self.assertEqual(self.client.post(reverse("machinery:machine_create"), self.payload).status_code, 403)

    def test_admin_create_read_update_delete(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("machinery:machine_create"), self.payload, follow=True)
        self.assertContains(r, "was added")
        m = Machine.objects.get()
        self.assertEqual(m.cooperative, self.coop)
        self.assertEqual(m.created_by, self.admin)
        self.assertContains(self.client.get(reverse("machinery:machine_list")), "Kubota Tractor")

        self.payload.update(name="Kubota L5018", status="maintenance")
        r = self.client.post(reverse("machinery:machine_edit", args=[m.pk]), self.payload, follow=True)
        self.assertContains(r, "was updated")
        m.refresh_from_db()
        self.assertEqual((m.name, m.status), ("Kubota L5018", "maintenance"))

        r = self.client.post(reverse("machinery:machine_delete", args=[m.pk]), follow=True)
        self.assertContains(r, "was deleted")
        self.assertFalse(Machine.objects.exists())

    def test_validation_errors(self):
        self.client.force_login(self.admin)
        bad = dict(self.payload, name="", hourly_rate="-5")
        r = self.client.post(reverse("machinery:machine_create"), bad)
        self.assertContains(r, "Machine not saved")
        self.assertFalse(Machine.objects.exists())
        self.client.post(reverse("machinery:machine_create"), self.payload)
        r = self.client.post(reverse("machinery:machine_create"), dict(self.payload, name="kubota tractor"))
        self.assertContains(r, "already has a machine with this name")

    def test_admin_cannot_touch_other_coop_machine(self):
        other_coop, other_admin = make_coop_admin("admin2", "Coop Two")
        m = Machine.objects.create(cooperative=other_coop, name="Their Tractor")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("machinery:machine_edit", args=[m.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("machinery:machine_delete", args=[m.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("machinery:machine_list")), "Their Tractor")

    def test_delete_requires_post(self):
        m = Machine.objects.create(cooperative=self.coop, name="T")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("machinery:machine_delete", args=[m.pk])).status_code, 405)
