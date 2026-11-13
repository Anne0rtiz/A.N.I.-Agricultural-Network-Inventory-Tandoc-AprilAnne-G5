import secrets

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

ph_mobile_validator = RegexValidator(
    regex=r"^(\+63|0)9\d{9}$",
    message="Enter a valid Philippine mobile number",
)


class Cooperative(models.Model):
    name = models.CharField(max_length=150, unique=True)
    location = models.CharField(max_length=200, blank=True)
    join_code = models.CharField(max_length=8, unique=True, editable=False, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.join_code:
            self.join_code = self._generate_join_code()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_join_code(cls):
        while True:
            code = "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(8))
            if not cls.objects.filter(join_code=code).exists():
                return code


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Cooperative Admin"
        FARMER = "farmer", "Farmer"

    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.FARMER)
    contact_number = models.CharField(
        max_length=13, blank=True, validators=[ph_mobile_validator]
    )
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)
    cooperative = models.ForeignKey(
        Cooperative,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="members",
    )
    farmer_code = models.CharField(
        max_length=20, unique=True, null=True, blank=True, editable=False
    )

    @property
    def is_coop_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_farmer(self):
        return self.role == self.Role.FARMER

    @property
    def dashboard_url_name(self):
        return "accounts:admin_dashboard" if self.is_coop_admin else "accounts:farmer_dashboard"

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)
        if self.role == self.Role.FARMER and not self.farmer_code:
            self.farmer_code = f"ANI-{self.pk:05d}"
            super().save(update_fields=["farmer_code"])
