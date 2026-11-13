from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from .models import Cooperative

User = get_user_model()

MAX_PHOTO_SIZE = 2 * 1024 * 1024


class RegistrationForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=User.Role.choices,
        initial=User.Role.FARMER,
        widget=forms.RadioSelect,
        label="I am registering as",
    )
    cooperative_name = forms.CharField(
        max_length=150, required=False, label="Cooperative name"
    )
    cooperative_location = forms.CharField(
        max_length=200, required=False, label="Location (barangay / municipality)"
    )
    join_code = forms.CharField(
        max_length=8,
        required=False,
        label="Cooperative join code",
        help_text="Ask your Cooperative Admin for the 8-character code.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username", "email", "contact_number")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cooperative = None
        for name in ("first_name", "last_name", "email", "contact_number"):
            self.fields[name].required = True
        self.fields["contact_number"].help_text = (
            "Mobile number for SMS alerts"
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")

        if role == User.Role.ADMIN:
            name = (cleaned.get("cooperative_name") or "").strip()
            if not name:
                self.add_error("cooperative_name", "Enter the name of your cooperative.")
            elif Cooperative.objects.filter(name__iexact=name).exists():
                self.add_error(
                    "cooperative_name", "A cooperative with this name is already registered."
                )
            else:
                cleaned["cooperative_name"] = name

        elif role == User.Role.FARMER:
            code = (cleaned.get("join_code") or "").strip().upper()
            if not code:
                self.add_error("join_code", "Enter the join code from your Cooperative Admin.")
            else:
                self._cooperative = Cooperative.objects.filter(join_code=code).first()
                if self._cooperative is None:
                    self.add_error(
                        "join_code",
                        "That join code is not valid. Please check with your Cooperative Admin.",
                    )
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data["role"]
        if user.role == User.Role.ADMIN:
            user.cooperative = Cooperative.objects.create(
                name=self.cleaned_data["cooperative_name"],
                location=(self.cleaned_data.get("cooperative_location") or "").strip(),
            )
        else:
            user.cooperative = self._cooperative
        user.save()
        return user


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Invalid username/email or password. Please try again.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username or email"


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "contact_number", "profile_photo")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email", "contact_number"):
            self.fields[name].required = True
        self.fields["profile_photo"].help_text = "JPG or PNG, up to 2 MB."

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another account already uses this email address.")
        return email

    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")
        if isinstance(photo, UploadedFile) and photo.size > MAX_PHOTO_SIZE:
            raise forms.ValidationError("Please upload an image smaller than 2 MB.")
        return photo
