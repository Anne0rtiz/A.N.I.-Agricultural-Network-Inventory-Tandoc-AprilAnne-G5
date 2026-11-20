from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from machinery.models import Machine, Reservation

from .test_machines import make_coop_admin, make_farmer


class ReservationBase(TestCase):
    def setUp(self):
        self.coop, self.admin = make_coop_admin()
        self.farmer = make_farmer(self.coop, "farmer1")
        self.farmer2 = make_farmer(self.coop, "farmer2")
        self.machine = Machine.objects.create(
            cooperative=self.coop, name="Tractor A", hourly_rate="100.00"
        )
        self.day = timezone.localdate() + timedelta(days=3)

    def payload(self, **over):
        data = {
            "machine": self.machine.pk, "date": self.day.isoformat(),
            "start_time": "08:00", "end_time": "10:00",
            "field_location": "Brgy. Sample, Plot 4", "purpose": "Land preparation",
        }
        data.update(over)
        return data

    def book(self, farmer=None, status=Reservation.Status.PENDING, **kw):
        defaults = dict(
            farmer=farmer or self.farmer, machine=self.machine, date=self.day,
            start_time="08:00", end_time="10:00", field_location="Plot", purpose="Plowing",
            status=status,
        )
        defaults.update(kw)
        return Reservation.objects.create(**defaults)


class FarmerReservationTests(ReservationBase):
    def test_login_required(self):
        r = self.client.get(reverse("machinery:my_reservations"))
        self.assertEqual(r.status_code, 302)

    def test_admin_cannot_use_farmer_pages(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("machinery:reservation_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("machinery:my_reservations")).status_code, 403)

    def test_create_and_read(self):
        self.client.force_login(self.farmer)
        r = self.client.post(reverse("machinery:reservation_create"), self.payload(), follow=True)
        self.assertContains(r, "Reservation request sent")
        res = Reservation.objects.get()
        self.assertEqual(res.farmer, self.farmer)
        self.assertEqual(res.status, "pending")
        self.assertEqual(str(res.estimated_cost), "200.00")
        self.assertContains(self.client.get(reverse("machinery:my_reservations")), "Tractor A")

    def test_validation_rules(self):
        self.client.force_login(self.farmer)
        url = reverse("machinery:reservation_create")
        cases = {
            "past date": (self.payload(date=(timezone.localdate() - timedelta(days=1)).isoformat()), "past date"),
            "end before start": (self.payload(start_time="10:00", end_time="09:00"), "later than the start"),
            "too long": (self.payload(start_time="06:00", end_time="18:00"), "exceed"),
            "after hours": (self.payload(start_time="03:00", end_time="05:00"), "between 5:00 AM"),
            "too far ahead": (self.payload(date=(timezone.localdate() + timedelta(days=90)).isoformat()), "days ahead"),
            "blank purpose": (self.payload(purpose="  "), "required"),
            "no location": (self.payload(field_location=""), "required"),
        }
        for label, (data, text) in cases.items():
            with self.subTest(label):
                r = self.client.post(url, data)
                self.assertContains(r, text)
        self.assertFalse(Reservation.objects.exists())

    def test_cannot_book_maintenance_or_other_coop_machine(self):
        other_coop, _ = make_coop_admin("admin9", "Other Coop")
        foreign = Machine.objects.create(cooperative=other_coop, name="Foreign")
        broken = Machine.objects.create(cooperative=self.coop, name="Broken", status="maintenance")
        self.client.force_login(self.farmer)
        for m in (foreign, broken):
            r = self.client.post(reverse("machinery:reservation_create"), self.payload(machine=m.pk))
            self.assertContains(r, "Select a valid choice")
        self.assertFalse(Reservation.objects.exists())

    def test_conflict_with_approved_booking_blocked(self):
        self.book(farmer=self.farmer2, status="approved", start_time="09:00", end_time="11:00")
        self.client.force_login(self.farmer)
        r = self.client.post(reverse("machinery:reservation_create"), self.payload())
        self.assertContains(r, "already booked")
        # adjacent slot is fine
        r = self.client.post(reverse("machinery:reservation_create"),
                             self.payload(start_time="11:00", end_time="12:00"))
        self.assertEqual(r.status_code, 302)

    def test_duplicate_own_pending_blocked(self):
        self.book()
        self.client.force_login(self.farmer)
        r = self.client.post(reverse("machinery:reservation_create"), self.payload())
        self.assertContains(r, "already have a pending request")

    def test_edit_only_when_pending(self):
        res = self.book()
        self.client.force_login(self.farmer)
        r = self.client.post(reverse("machinery:reservation_edit", args=[res.pk]),
                             self.payload(end_time="11:00"), follow=True)
        self.assertContains(r, "updated")
        res.refresh_from_db()
        self.assertEqual(res.end_time.hour, 11)
        res.status = "approved"; res.save()
        r = self.client.get(reverse("machinery:reservation_edit", args=[res.pk]), follow=True)
        self.assertContains(r, "Only pending")

    def test_cancel_and_delete(self):
        res = self.book()
        self.client.force_login(self.farmer)
        self.client.post(reverse("machinery:reservation_delete", args=[res.pk]))
        self.assertTrue(Reservation.objects.filter(pk=res.pk).exists())  # must cancel first
        self.client.post(reverse("machinery:reservation_cancel", args=[res.pk]))
        res.refresh_from_db()
        self.assertEqual(res.status, "cancelled")
        self.client.post(reverse("machinery:reservation_delete", args=[res.pk]))
        self.assertFalse(Reservation.objects.filter(pk=res.pk).exists())

    def test_farmer_cannot_access_others_records(self):
        res = self.book(farmer=self.farmer2)
        self.client.force_login(self.farmer)
        for name in ("reservation_detail", "reservation_edit"):
            self.assertEqual(self.client.get(reverse(f"machinery:{name}", args=[res.pk])).status_code, 404)
        for name in ("reservation_cancel", "reservation_delete"):
            self.assertEqual(self.client.post(reverse(f"machinery:{name}", args=[res.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("machinery:my_reservations")), "Tractor A")

    def test_catalog_and_dashboard_widget(self):
        self.book()
        self.client.force_login(self.farmer)
        self.assertContains(self.client.get(reverse("machinery:machine_catalog")), "Tractor A")
        self.assertContains(self.client.get(reverse("accounts:farmer_dashboard")), "My machinery reservations")


class AdminReviewTests(ReservationBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def review(self, res, decision, remarks=""):
        return self.client.post(
            reverse("machinery:reservation_review", args=[res.pk]),
            {"decision": decision, "remarks": remarks}, follow=True,
        )

    def test_farmer_cannot_review(self):
        res = self.book()
        self.client.force_login(self.farmer)
        self.assertEqual(self.client.post(reverse("machinery:reservation_review", args=[res.pk]),
                                          {"decision": "approve"}).status_code, 403)

    def test_approve_records_reviewer(self):
        res = self.book()
        self.assertContains(self.review(res, "approve", "OK"), "approved")
        res.refresh_from_db()
        self.assertEqual((res.status, res.reviewed_by, res.admin_remarks), ("approved", self.admin, "OK"))
        self.assertIsNotNone(res.reviewed_at)

    def test_reject_needs_reason(self):
        res = self.book()
        self.assertContains(self.review(res, "reject"), "reason")
        res.refresh_from_db()
        self.assertEqual(res.status, "pending")
        self.review(res, "reject", "Machine under repair")
        res.refresh_from_db()
        self.assertEqual(res.status, "rejected")

    def test_cannot_double_book_on_approval(self):
        a = self.book(farmer=self.farmer)
        b = self.book(farmer=self.farmer2, start_time="09:00", end_time="11:00")
        self.review(a, "approve")
        self.assertContains(self.review(b, "approve"), "overlaps")
        b.refresh_from_db()
        self.assertEqual(b.status, "pending")

    def test_cannot_review_twice(self):
        res = self.book()
        self.review(res, "approve")
        self.assertContains(self.review(res, "reject", "changed mind"), "already reviewed")

    def test_complete_only_after_date(self):
        res = self.book(status="approved")
        self.assertContains(self.client.post(reverse("machinery:reservation_complete", args=[res.pk]), follow=True),
                            "hasn&#x27;t taken place")
        res.date = timezone.localdate(); res.save()
        self.client.post(reverse("machinery:reservation_complete", args=[res.pk]))
        res.refresh_from_db()
        self.assertEqual(res.status, "completed")

    def test_admin_isolated_by_cooperative(self):
        other_coop, other_admin = make_coop_admin("admin2", "Other")
        res = self.book()
        self.client.force_login(other_admin)
        self.assertEqual(self.client.get(reverse("machinery:reservation_detail", args=[res.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("machinery:reservation_review", args=[res.pk]),
                                          {"decision": "approve"}).status_code, 404)
        self.assertNotContains(self.client.get(reverse("machinery:reservation_manage")), "farmer1")

    def test_manage_list_filter_and_dashboard(self):
        self.book()
        self.book(farmer=self.farmer2, status="approved", start_time="12:00", end_time="13:00")
        r = self.client.get(reverse("machinery:reservation_manage") + "?status=pending")
        self.assertContains(r, "farmer1"); self.assertNotContains(r, "farmer2")
        d = self.client.get(reverse("accounts:admin_dashboard"))
        self.assertContains(d, "Pending machinery requests")

    def test_machine_with_reservations_cannot_be_deleted(self):
        self.book()
        r = self.client.post(reverse("machinery:machine_delete", args=[self.machine.pk]), follow=True)
        self.assertContains(r, "can&#x27;t be deleted")
        self.assertTrue(Machine.objects.filter(pk=self.machine.pk).exists())
