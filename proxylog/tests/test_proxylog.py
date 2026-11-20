from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from machinery.models import Machine, Reservation
from machinery.tests.test_machines import make_coop_admin, make_farmer
from proxylog.models import CropDeposit, EquipmentRental


class Base(TestCase):
    def setUp(self):
        self.coop, self.admin = make_coop_admin()
        self.farmer = make_farmer(self.coop, "farmer1")
        self.farmer2 = make_farmer(self.coop, "farmer2")
        self.machine = Machine.objects.create(cooperative=self.coop, name="Tractor A")
        self.client.force_login(self.admin)

    def deposit_payload(self, **o):
        d = {"crop_type": "rice", "weight_kg": "120.50", "grade": "A", "notes": ""}
        d.update(o); return d

    def rental_payload(self, **o):
        d = {"machine": self.machine.pk, "expected_hours": "2.0", "notes": ""}
        d.update(o); return d


class ScanTests(Base):
    def test_requires_login_and_admin_role(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("proxylog:scan")).status_code, 302)
        self.client.force_login(self.farmer)
        for name in ("scan", "transaction_log", "card_list"):
            self.assertEqual(self.client.get(reverse(f"proxylog:{name}")).status_code, 403)
        self.assertEqual(self.client.post(reverse("proxylog:deposit_create", args=[self.farmer.farmer_code]),
                                          self.deposit_payload()).status_code, 403)

    def test_scan_valid_code_case_insensitive(self):
        r = self.client.post(reverse("proxylog:scan"), {"farmer_code": f" {self.farmer.farmer_code.lower()} "})
        self.assertRedirects(r, reverse("proxylog:farmer_workspace", args=[self.farmer.farmer_code]))

    def test_scan_invalid_and_other_coop(self):
        other_coop, _ = make_coop_admin("admin2", "Other")
        stranger = make_farmer(other_coop, "stranger")
        for code in ("ANI-99999", stranger.farmer_code):
            r = self.client.post(reverse("proxylog:scan"), {"farmer_code": code})
            self.assertContains(r, "No farmer with ID")
        self.assertEqual(self.client.get(reverse("proxylog:farmer_workspace", args=[stranger.farmer_code])).status_code, 404)

    def test_scan_empty(self):
        self.assertContains(self.client.post(reverse("proxylog:scan"), {"farmer_code": ""}), "Scan a QR card")


class DepositTests(Base):
    def test_create_read_update_delete(self):
        url = reverse("proxylog:deposit_create", args=[self.farmer.farmer_code])
        r = self.client.post(url, self.deposit_payload(), follow=True)
        self.assertContains(r, "Logged 120.50 kg")
        d = CropDeposit.objects.get()
        self.assertEqual((d.farmer, d.logged_by, d.cooperative), (self.farmer, self.admin, self.coop))
        self.assertContains(self.client.get(reverse("proxylog:transaction_log")), "120.50 kg")
        r = self.client.post(reverse("proxylog:deposit_edit", args=[d.pk]), self.deposit_payload(weight_kg="99"), follow=True)
        self.assertContains(r, "updated")
        d.refresh_from_db(); self.assertEqual(d.weight_kg, Decimal("99"))
        self.client.post(reverse("proxylog:deposit_delete", args=[d.pk]))
        self.assertFalse(CropDeposit.objects.exists())

    def test_validation(self):
        url = reverse("proxylog:deposit_create", args=[self.farmer.farmer_code])
        for data, text in [({"weight_kg": "0"}, "greater than"), ({"weight_kg": "-4"}, "greater than"),
                           ({"weight_kg": "60000"}, "exceed"), ({"weight_kg": ""}, "required"),
                           ({"crop_type": ""}, "required"), ({"weight_kg": "abc"}, "number")]:
            with self.subTest(data):
                self.assertContains(self.client.post(url, self.deposit_payload(**data)), text)
        self.assertFalse(CropDeposit.objects.exists())

    def test_isolation_between_cooperatives(self):
        other_coop, other_admin = make_coop_admin("admin2", "Other")
        d = CropDeposit.objects.create(cooperative=self.coop, farmer=self.farmer, crop_type="rice", weight_kg=5)
        self.client.force_login(other_admin)
        self.assertEqual(self.client.get(reverse("proxylog:deposit_edit", args=[d.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("proxylog:deposit_delete", args=[d.pk])).status_code, 404)

    def test_delete_requires_post(self):
        d = CropDeposit.objects.create(cooperative=self.coop, farmer=self.farmer, crop_type="rice", weight_kg=5)
        self.assertEqual(self.client.get(reverse("proxylog:deposit_delete", args=[d.pk])).status_code, 405)


class RentalTests(Base):
    def url(self, farmer=None):
        return reverse("proxylog:rental_create", args=[(farmer or self.farmer).farmer_code])

    def test_checkout_and_return(self):
        r = self.client.post(self.url(), self.rental_payload(), follow=True)
        self.assertContains(r, "checked out")
        rental = EquipmentRental.objects.get()
        self.assertTrue(rental.is_active)
        r = self.client.post(reverse("proxylog:rental_return", args=[rental.pk]), follow=True)
        self.assertContains(r, "returned")
        rental.refresh_from_db(); self.assertEqual(rental.status, "returned"); self.assertIsNotNone(rental.returned_at)
        self.assertContains(self.client.post(reverse("proxylog:rental_return", args=[rental.pk]), follow=True), "already returned")

    def test_machine_already_out(self):
        self.client.post(self.url(), self.rental_payload())
        self.assertContains(self.client.post(self.url(self.farmer2), self.rental_payload()), "still out on rental")
        self.assertEqual(EquipmentRental.objects.count(), 1)

    def test_validation(self):
        for data, text in [({"expected_hours": "0"}, "between 0.5 and 12"), ({"expected_hours": "20"}, "between 0.5 and 12"),
                           ({"machine": ""}, "required")]:
            with self.subTest(data):
                self.assertContains(self.client.post(self.url(), self.rental_payload(**data)), text)
        self.machine.status = "maintenance"; self.machine.save()
        self.assertContains(self.client.post(self.url(), self.rental_payload()), "Select a valid choice")

    def _reserve(self, farmer):
        now = timezone.localtime()
        start = (now - timedelta(minutes=10)).time(); end = (now + timedelta(hours=3)).time()
        if end < start or now.hour >= 20:  # keep the window inside one day regardless of clock
            self.skipTest("too close to midnight")
        return Reservation.objects.create(
            farmer=farmer, machine=self.machine, date=timezone.localdate(), start_time=start, end_time=end,
            field_location="x", purpose="Plowing", status="approved")

    def test_blocked_by_other_farmers_reservation(self):
        self._reserve(self.farmer2)
        self.assertContains(self.client.post(self.url(), self.rental_payload()), "reserved by another farmer")

    def test_own_reservation_is_linked_and_completed_on_return(self):
        res = self._reserve(self.farmer)
        self.client.post(self.url(), self.rental_payload())
        rental = EquipmentRental.objects.get(); self.assertEqual(rental.reservation, res)
        self.client.post(reverse("proxylog:rental_return", args=[rental.pk]))
        res.refresh_from_db(); self.assertEqual(res.status, "completed")

    def test_delete_rental_and_machine_protection(self):
        self.client.post(self.url(), self.rental_payload())
        rental = EquipmentRental.objects.get()
        r = self.client.post(reverse("machinery:machine_delete", args=[self.machine.pk]), follow=True)
        self.assertContains(r, "can&#x27;t be deleted")
        self.client.post(reverse("proxylog:rental_delete", args=[rental.pk]))
        self.assertFalse(EquipmentRental.objects.exists())


class FarmerViewsTests(Base):
    def test_qr_card_and_contributions_are_own_only(self):
        CropDeposit.objects.create(cooperative=self.coop, farmer=self.farmer, crop_type="rice", weight_kg=10)
        CropDeposit.objects.create(cooperative=self.coop, farmer=self.farmer2, crop_type="corn", weight_kg=77)
        self.client.force_login(self.farmer)
        card = self.client.get(reverse("proxylog:my_qr"))
        self.assertContains(card, self.farmer.farmer_code)
        r = self.client.get(reverse("proxylog:my_contributions"))
        self.assertContains(r, "10.00 kg"); self.assertNotContains(r, "77.00")
        self.assertEqual(self.client.get(reverse("proxylog:card_list")).status_code, 403)

    def test_admin_cannot_open_farmer_pages(self):
        self.assertEqual(self.client.get(reverse("proxylog:my_qr")).status_code, 403)

    def test_admin_card_print_and_dashboards(self):
        CropDeposit.objects.create(cooperative=self.coop, farmer=self.farmer, crop_type="rice", weight_kg=10)
        self.assertContains(self.client.get(reverse("proxylog:card_print", args=[self.farmer.farmer_code])), self.farmer.farmer_code)
        self.assertContains(self.client.get(reverse("accounts:admin_dashboard")), "Cooperative yields")
        self.client.force_login(self.farmer)
        self.assertContains(self.client.get(reverse("accounts:farmer_dashboard")), "Total deposited")

    def test_transaction_log_filter_search(self):
        CropDeposit.objects.create(cooperative=self.coop, farmer=self.farmer, crop_type="rice", weight_kg=10)
        EquipmentRental.objects.create(cooperative=self.coop, farmer=self.farmer2, machine=self.machine, expected_hours=1)
        r = self.client.get(reverse("proxylog:transaction_log") + "?type=deposits")
        self.assertContains(r, "No rentals found" if False else "Crop drop-offs"); self.assertNotContains(r, "Tractor A")
        r = self.client.get(reverse("proxylog:transaction_log") + f"?q={self.farmer2.farmer_code}")
        self.assertContains(r, "Tractor A"); self.assertNotContains(r, "10.00 kg</td>")
