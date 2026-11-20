from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Machine(models.Model):
    """A piece of cooperative-owned farm machinery that farmers can reserve."""

    class MachineType(models.TextChoices):
        TRACTOR = "tractor", "Tractor"
        HARVESTER = "harvester", "Harvester"
        THRESHER = "thresher", "Thresher"
        PUMP = "pump", "Water pump"
        SPRAYER = "sprayer", "Sprayer"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        MAINTENANCE = "maintenance", "Under maintenance"

    cooperative = models.ForeignKey(
        "accounts.Cooperative", on_delete=models.CASCADE, related_name="machines"
    )
    name = models.CharField(max_length=100)
    machine_type = models.CharField(
        max_length=20, choices=MachineType.choices, default=MachineType.TRACTOR
    )
    description = models.TextField(blank=True)
    hourly_rate = models.DecimalField(
        "rate per hour (PHP)",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.AVAILABLE
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="machines_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["cooperative", "name"], name="unique_machine_name_per_coop"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_machine_type_display()})"

    @property
    def is_available(self):
        return self.status == self.Status.AVAILABLE


class Reservation(models.Model):
    """A farmer's request to use a machine on a given date and time window."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    farmer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    machine = models.ForeignKey(
        Machine, on_delete=models.PROTECT, related_name="reservations"
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    field_location = models.CharField("field / farm location", max_length=200)
    purpose = models.TextField("purpose of use")
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    admin_remarks = models.CharField(max_length=300, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-start_time"]

    def __str__(self):
        return f"{self.machine.name} · {self.date} {self.start_time:%H:%M}-{self.end_time:%H:%M}"

    @property
    def duration_hours(self):
        start = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        return Decimal((end - start) / timedelta(hours=1)).quantize(Decimal("0.01"))

    @property
    def estimated_cost(self):
        return (self.duration_hours * self.machine.hourly_rate).quantize(Decimal("0.01"))

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_editable(self):
        return self.status == self.Status.PENDING

    @property
    def is_cancellable(self):
        return self.status in (self.Status.PENDING, self.Status.APPROVED)

    @property
    def is_deletable(self):
        return self.status in (
            self.Status.CANCELLED,
            self.Status.REJECTED,
            self.Status.COMPLETED,
        )

    def overlapping(self, statuses):
        """Other reservations for the same machine/date whose time window overlaps."""
        return (
            Reservation.objects.filter(
                machine_id=self.machine_id,
                date=self.date,
                status__in=statuses,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            )
            .exclude(pk=self.pk)
            .select_related("farmer")
        )

    def has_approved_conflict(self):
        return self.overlapping([self.Status.APPROVED]).exists()
