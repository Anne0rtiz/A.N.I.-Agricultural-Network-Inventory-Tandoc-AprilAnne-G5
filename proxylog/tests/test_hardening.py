"""PD3 hardening tests: error pages, database constraints, access control and PRG."""
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse

from proxylog.models import CropDeposit, EquipmentRental
from proxylog.tests.test_proxylog import Base


class ErrorPageTests(Base):
    def test_debug_is_off_in_tests(self):
        self.assertFalse(settings.DEBUG)

    def test_custom_404_for_unknown_url(self):
        r = self.client.get("/this/page/does/not/exist/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "Page not found", status_code=404)

    def test_invalid_ids_return_404_not_crash(self):
        for name in ("deposit_edit",):
            self.assertEqual(self.client.get(reverse(f"proxylog:{name}", args=[99999])).status_code, 404)
        for name in ("deposit_delete", "rental_return", "rental_delete"):
            self.assertEqual(self.client.post(reverse(f"proxylog:{name}", args=[99999])).status_code, 404)

    def test_custom_500_page_has_no_traceback(self):
        client = Client(raise_request_exception=False)
        client.force_login(self.admin)
        with mock.patch("proxylog.views.qr_data_uri", side_effect=RuntimeError("secret internals")):
            r = client.get(reverse("proxylog:card_print", args=[self.farmer.farmer_code]))
        self.assertEqual(r.status_code, 500)
        self.assertContains(r, "Something went wrong", status_code=500)
        self.assertNotContains(r, "secret internals", status_code=500)
        self.assertNotContains(r, "Traceback", status_code=500)


class ConstraintTests(Base):
    def test_db_blocks_second_active_rental_for_same_machine(self):
        EquipmentRental.objects.create(
            cooperative=self.coop, farmer=self.farmer, machine=self.machine, expected_hours=Decimal("2.0"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            EquipmentRental.objects.create(
                cooperative=self.coop, farmer=self.farmer2, machine=self.machine, expected_hours=Decimal("1.0"))

    def test_returned_rental_does_not_block_new_rental(self):
        EquipmentRental.objects.create(
            cooperative=self.coop, farmer=self.farmer, machine=self.machine,
            expected_hours=Decimal("2.0"), status="returned")
        EquipmentRental.objects.create(
            cooperative=self.coop, farmer=self.farmer2, machine=self.machine, expected_hours=Decimal("1.0"))
        self.assertEqual(EquipmentRental.objects.filter(machine=self.machine).count(), 2)

    def test_db_rejects_non_positive_weight(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CropDeposit.objects.create(
                cooperative=self.coop, farmer=self.farmer, crop_type="rice", weight_kg=Decimal("0"))

    def test_db_rejects_rental_hours_out_of_range(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            EquipmentRental.objects.create(
                cooperative=self.coop, farmer=self.farmer, machine=self.machine, expected_hours=Decimal("13.0"))


class RedirectAndAccessTests(Base):
    def test_successful_posts_redirect_to_prevent_double_submit(self):
        r = self.client.post(reverse("proxylog:deposit_create", args=[self.farmer.farmer_code]),
                             self.deposit_payload())
        self.assertEqual(r.status_code, 302)
        r = self.client.post(reverse("proxylog:rental_create", args=[self.farmer.farmer_code]),
                             self.rental_payload())
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CropDeposit.objects.count(), 1)
        self.assertEqual(EquipmentRental.objects.count(), 1)

    def test_second_checkout_of_same_machine_is_rejected_with_message(self):
        url = reverse("proxylog:rental_create", args=[self.farmer.farmer_code])
        self.client.post(url, self.rental_payload())
        r = self.client.post(reverse("proxylog:rental_create", args=[self.farmer2.farmer_code]),
                             self.rental_payload())
        self.assertContains(r, "still out on rental")
        self.assertEqual(EquipmentRental.objects.count(), 1)

    def test_farmer_cannot_edit_or_delete_log_entries_by_id(self):
        deposit = CropDeposit.objects.create(
            cooperative=self.coop, farmer=self.farmer, crop_type="rice", weight_kg=Decimal("10"))
        self.client.force_login(self.farmer)
        self.assertEqual(self.client.get(reverse("proxylog:deposit_edit", args=[deposit.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("proxylog:deposit_delete", args=[deposit.pk])).status_code, 403)
        self.assertTrue(CropDeposit.objects.filter(pk=deposit.pk).exists())

    def test_admin_cannot_touch_other_cooperatives_entries(self):
        from machinery.tests.test_machines import make_coop_admin, make_farmer
        other_coop, other_admin = make_coop_admin("admin2", "Other Coop")
        stranger = make_farmer(other_coop, "stranger")
        deposit = CropDeposit.objects.create(
            cooperative=other_coop, farmer=stranger, crop_type="corn", weight_kg=Decimal("5"))
        self.assertEqual(self.client.get(reverse("proxylog:deposit_edit", args=[deposit.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("proxylog:deposit_delete", args=[deposit.pk])).status_code, 404)
        self.assertTrue(CropDeposit.objects.filter(pk=deposit.pk).exists())
