from datetime import datetime, time, timedelta

from django import forms
from django.utils import timezone

from .models import Machine, Reservation


class MachineForm(forms.ModelForm):
    class Meta:
        model = Machine
        fields = ("name", "machine_type", "description", "hourly_rate", "status")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, cooperative=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cooperative = cooperative or getattr(self.instance, "cooperative", None)
        self.fields["hourly_rate"].help_text = "Use 0 if the machine is free for members."

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Machine name is required.")
        duplicate = Machine.objects.filter(
            cooperative=self.cooperative, name__iexact=name
        ).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("Your cooperative already has a machine with this name.")
        return name

    def clean_hourly_rate(self):
        rate = self.cleaned_data["hourly_rate"]
        if rate < 0:
            raise forms.ValidationError("The rate cannot be negative.")
        return rate


MAX_HOURS = 10
OPEN_TIME = time(5, 0)
CLOSE_TIME = time(20, 0)
MAX_ADVANCE_DAYS = 60


class ReservationForm(forms.ModelForm):
    """Farmer's booking form. All business rules live in clean()."""

    class Meta:
        model = Reservation
        fields = ("machine", "date", "start_time", "end_time", "field_location", "purpose")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "purpose": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, farmer, **kwargs):
        super().__init__(*args, **kwargs)
        self.farmer = farmer
        self.fields["machine"].queryset = Machine.objects.filter(
            cooperative_id=farmer.cooperative_id, status=Machine.Status.AVAILABLE
        )
        self.fields["machine"].empty_label = "Select a machine…"
        self.fields["start_time"].help_text = "Machines operate 5:00 AM – 8:00 PM."
        self.fields["purpose"].help_text = "e.g. Land preparation, harvesting, irrigation."

    def clean_field_location(self):
        value = self.cleaned_data["field_location"].strip()
        if not value:
            raise forms.ValidationError("Tell us where the machine will be used.")
        return value

    def clean_purpose(self):
        value = self.cleaned_data["purpose"].strip()
        if len(value) < 5:
            raise forms.ValidationError("Please describe the purpose (at least 5 characters).")
        return value

    def clean_date(self):
        day = self.cleaned_data["date"]
        today = timezone.localdate()
        if day < today:
            raise forms.ValidationError("You can't reserve a machine for a past date.")
        if day > today + timedelta(days=MAX_ADVANCE_DAYS):
            raise forms.ValidationError(
                f"Reservations can only be made up to {MAX_ADVANCE_DAYS} days ahead."
            )
        return day

    def clean(self):
        cleaned = super().clean()
        machine = cleaned.get("machine")
        day = cleaned.get("date")
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if not (machine and day and start and end):
            return cleaned

        if end <= start:
            self.add_error("end_time", "End time must be later than the start time.")
            return cleaned
        if start < OPEN_TIME or end > CLOSE_TIME:
            self.add_error("start_time", "Reservations must be between 5:00 AM and 8:00 PM.")
            return cleaned
        if day == timezone.localdate() and start <= timezone.localtime().time():
            self.add_error("start_time", "That start time has already passed today.")
            return cleaned

        hours = (datetime.combine(day, end) - datetime.combine(day, start)) / timedelta(hours=1)
        if hours > MAX_HOURS:
            self.add_error("end_time", f"A single reservation can't exceed {MAX_HOURS} hours.")
            return cleaned

        draft = Reservation(machine=machine, date=day, start_time=start, end_time=end)
        draft.pk = self.instance.pk
        if draft.has_approved_conflict():
            raise forms.ValidationError(
                "This machine is already booked during that time. Please pick another time slot."
            )
        own = draft.overlapping([Reservation.Status.PENDING]).filter(farmer=self.farmer)
        if own.exists():
            raise forms.ValidationError(
                "You already have a pending request for this machine that overlaps this time."
            )
        return cleaned


class ReviewForm(forms.Form):
    """Admin's approve / reject decision."""

    remarks = forms.CharField(max_length=300, required=False)
    decision = forms.ChoiceField(choices=[("approve", "Approve"), ("reject", "Reject")])

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("decision") == "reject" and not (cleaned.get("remarks") or "").strip():
            self.add_error("remarks", "Please give a short reason when rejecting a request.")
        return cleaned
