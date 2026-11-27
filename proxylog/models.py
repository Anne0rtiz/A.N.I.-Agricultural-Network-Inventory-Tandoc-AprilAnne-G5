from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class CropDeposit(models.Model):
    """Harvest dropped off at the cooperative hub, logged by an admin for a farmer."""

    class CropType(models.TextChoices):
        RICE = "rice", "Palay (rice)"
        CORN = "corn", "Corn"
        COCONUT = "coconut", "Coconut"
        BANANA = "banana", "Banana"
        VEGETABLES = "vegetables", "Vegetables"
        OTHER = "other", "Other"

    class Grade(models.TextChoices):
        A = "A", "Grade A"
        B = "B", "Grade B"
        C = "C", "Grade C"

    cooperative = models.ForeignKey(
        "accounts.Cooperative", on_delete=models.CASCADE, related_name="crop_deposits"
    )
    farmer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="crop_deposits"
    )
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="crop_deposits_logged",
    )
    crop_type = models.CharField(max_length=20, choices=CropType.choices)
    weight_kg = models.DecimalField(
        "weight (kg)", max_digits=9, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    grade = models.CharField(max_length=1, choices=Grade.choices, default=Grade.A)
    notes = models.CharField(max_length=200, blank=True)
    deposited_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-deposited_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weight_kg__gt=0), name="deposit_weight_positive"
            ),
        ]

    def __str__(self):
        return f"{self.farmer.farmer_code} · {self.get_crop_type_display()} {self.weight_kg} kg"


class EquipmentRental(models.Model):
    """A machine handed to a farmer at the hub (walk-in rental), logged by an admin."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Out on rental"
        RETURNED = "returned", "Returned"

    cooperative = models.ForeignKey(
        "accounts.Cooperative", on_delete=models.CASCADE, related_name="equipment_rentals"
    )
    farmer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="equipment_rentals"
    )
    machine = models.ForeignKey(
        "machinery.Machine", on_delete=models.PROTECT, related_name="rentals"
    )
    reservation = models.ForeignKey(
        "machinery.Reservation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rentals",
    )
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="rentals_logged",
    )
    start_at = models.DateTimeField(default=timezone.now)
    expected_hours = models.DecimalField(
        max_digits=4, decimal_places=1, validators=[MinValueValidator(Decimal("0.5"))]
    )
    returned_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_at"]
        constraints = [
            # A machine can be out on only one active rental at a time (fixes PD2 ISS-03).
            models.UniqueConstraint(
                fields=["machine"],
                condition=models.Q(status="active"),
                name="one_active_rental_per_machine",
            ),
            models.CheckConstraint(
                condition=models.Q(expected_hours__gte=Decimal("0.5"), expected_hours__lte=Decimal("12")),
                name="rental_hours_between_0_5_and_12",
            ),
        ]

    def __str__(self):
        return f"{self.machine.name} → {self.farmer.farmer_code}"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def due_at(self):
        return self.start_at + timedelta(hours=float(self.expected_hours))

    @property
    def is_overdue(self):
        return self.is_active and timezone.now() > self.due_at

    @property
    def hours_used(self):
        end = self.returned_at or timezone.now()
        return Decimal((end - self.start_at) / timedelta(hours=1)).quantize(Decimal("0.1"))


def reservation_window(reservation):
    """Aware (start, end) datetimes of a machinery Reservation."""
    tz = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(reservation.date, reservation.start_time), tz),
        timezone.make_aware(datetime.combine(reservation.date, reservation.end_time), tz),
    )
