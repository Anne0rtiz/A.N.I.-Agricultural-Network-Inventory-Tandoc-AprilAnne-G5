from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import LoginForm, ProfileForm, RegistrationForm
from .models import User


def home(request):
    if request.user.is_authenticated:
        return redirect(request.user.dashboard_url_name)
    return render(request, "home.html")


def register(request):
    if request.user.is_authenticated:
        return redirect(request.user.dashboard_url_name)

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Account created successfully, {user.first_name}! You can now log in.",
            )
            return redirect("accounts:login")
        messages.error(request, "We couldn't create your account. Please fix the errors below.")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


class AniLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Welcome back, {form.get_user().display_name}!")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username/email or password. Please try again.")
        return super().form_invalid(form)


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("accounts:login")


@login_required
def dashboard_redirect(request):
    return redirect(request.user.dashboard_url_name)


@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    cooperative = request.user.cooperative
    farmers = User.objects.none()
    if cooperative is not None:
        farmers = cooperative.members.filter(role=User.Role.FARMER)
    context = {
        "cooperative": cooperative,
        "farmer_count": farmers.count(),
        "recent_farmers": farmers.order_by("-date_joined")[:5],
    }
    return render(request, "accounts/dashboard_admin.html", context)


@role_required(User.Role.FARMER)
def farmer_dashboard(request):
    return render(
        request,
        "accounts/dashboard_farmer.html",
        {"cooperative": request.user.cooperative},
    )


@login_required
def profile(request):
    return render(request, "accounts/profile.html", {"profile_user": request.user})


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")
        messages.error(request, "Error! Profile not saved.")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})
