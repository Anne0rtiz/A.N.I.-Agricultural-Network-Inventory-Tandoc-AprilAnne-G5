from datetime import timedelta
from decimal import Decimal

from django import forms
from django.utils import timezone

from machinery.models import Machine, Reservation

from .models import CropDeposit, EquipmentRental, reservation_window

MAX_DEPOSIT_KG = Decimal("50000")
MAX_RENTAL_HOURS = Decimal("12")


class ScanForm(forms.Form):
    farmer_code = forms.CharField(
        max_length=20, label="Farmer ID",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "off",
                                      "placeholder": "Scan the QR card or type ANI-00012"}),
    )

    def clean_farmer_code(self):
        return self.cleaned_data["farmer_code"].strip().upper()


class CropDepositForm(forms.ModelForm):
    class Meta:
        model = CropDeposit
        fields = ("crop_type", "weight_kg", "grade", "notes")

    def clean_weight_kg(self):
        weight = self.cleaned_data["weight_kg"]
        if weight <= 0:
            raise forms.ValidationError("Weight must be greater than zero.")
        if weight > MAX_DEPOSIT_KG:
            raise forms.ValidationError(f"Weight can't exceed {MAX_DEPOSIT_KG:,} kg per drop-off.")
        return weight


class RentalForm(forms.ModelForm):
    class Meta:
        model = EquipmentRental
        fields = ("machine", "expected_hours", "notes")

    def __init__(self, *args, cooperative, farmer, **kwargs):
        super().__init__(*args, **kwargs)
        self.farmer = farmer
        self.cooperative = cooperative
        self.fields["machine"].queryset = Machine.objects.filter(
            cooperative=cooperative, status=Machine.Status.AVAILABLE
        )
        self.fields["machine"].empty_label = "Select a machine…"
        self.fields["expected_hours"].help_text = "How long the farmer plans to use it (0.5 – 12)."
        self._reservation = None

    def clean_expected_hours(self):
        hours = self.cleaned_data["expected_hours"]
        if hours < Decimal("0.5") or hours > MAX_RENTAL_HOURS:
            raise forms.ValidationError("Expected hours must be between 0.5 and 12.")
        return hours

    def clean(self):
        cleaned = super().clean()
        machine, hours = cleaned.get("machine"), cleaned.get("expected_hours")
        if not (machine and hours):
            return cleaned
        if EquipmentRental.objects.filter(machine=machine, status=EquipmentRental.Status.ACTIVE).exists():
            raise forms.ValidationError(f"{machine.name} is still out on rental. Log its return first.")

        start = timezone.now()
        end = start + timedelta(hours=float(hours))
        nearby = Reservation.objects.filter(
            machine=machine,
            status=Reservation.Status.APPROVED,
            date__range=(timezone.localdate() - timedelta(days=1), timezone.localdate() + timedelta(days=1)),
        ).select_related("farmer")
        for res in nearby:
            res_start, res_end = reservation_window(res)
            if not (res_start < end and res_end > start):
                continue
            if res.farmer_id == self.farmer.pk:
                self._reservation = res  # farmer is collecting their own booking
            else:
                raise forms.ValidationError(
                    f"{machine.name} is reserved by another farmer from "
                    f"{res_start:%I:%M %p} to {res_end:%I:%M %p}. Choose a shorter time or another machine."
                )
        return cleaned

    @property
    def linked_reservation(self):
        return self._reservation
