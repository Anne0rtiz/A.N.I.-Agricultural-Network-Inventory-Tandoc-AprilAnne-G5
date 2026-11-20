from django import forms

from .models import Machine


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
