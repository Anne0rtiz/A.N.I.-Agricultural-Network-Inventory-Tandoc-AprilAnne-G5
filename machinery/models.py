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
