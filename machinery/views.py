from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import MachineForm, ReservationForm, ReviewForm
from .models import Machine, Reservation

admin_only = role_required(User.Role.ADMIN)
farmer_only = role_required(User.Role.FARMER)
any_role = role_required(User.Role.ADMIN, User.Role.FARMER)


def _coop_machines(user):
    """Machines belonging to the admin's cooperative (none if not linked)."""
    if user.cooperative_id is None:
        return Machine.objects.none()
    return Machine.objects.filter(cooperative_id=user.cooperative_id)


@admin_only
def machine_list(request):
    machines = _coop_machines(request.user)
    return render(request, "machinery/machine_list.html", {"machines": machines})


@admin_only
def machine_create(request):
    if request.user.cooperative_id is None:
        messages.error(request, "Your account isn't linked to a cooperative yet.")
        return redirect("machinery:machine_list")
    if request.method == "POST":
        form = MachineForm(request.POST, cooperative=request.user.cooperative)
        if form.is_valid():
            machine = form.save(commit=False)
            machine.cooperative = request.user.cooperative
            machine.created_by = request.user
            machine.save()
            messages.success(request, f"{machine.name} was added to your machinery list.")
            return redirect("machinery:machine_list")
        messages.error(request, "Machine not saved. Please fix the errors below.")
    else:
        form = MachineForm(cooperative=request.user.cooperative)
    return render(request, "machinery/machine_form.html", {"form": form, "is_edit": False})


@admin_only
def machine_edit(request, pk):
    machine = get_object_or_404(_coop_machines(request.user), pk=pk)
    if request.method == "POST":
        form = MachineForm(request.POST, instance=machine)
        if form.is_valid():
            form.save()
            messages.success(request, f"{machine.name} was updated.")
            return redirect("machinery:machine_list")
        messages.error(request, "Changes not saved. Please fix the errors below.")
    else:
        form = MachineForm(instance=machine)
    return render(
        request,
        "machinery/machine_form.html",
        {"form": form, "machine": machine, "is_edit": True},
    )


@admin_only
@require_POST
def machine_delete(request, pk):
    machine = get_object_or_404(_coop_machines(request.user), pk=pk)
    try:
        machine.delete()
    except ProtectedError:
        messages.error(
            request,
            f"{machine.name} has reservation records and can't be deleted. "
            "Set it to 'Under maintenance' instead.",
        )
    else:
        messages.success(request, f"{machine.name} was deleted.")
    return redirect("machinery:machine_list")


# --------------------------------------------------------------------------
# Farmer: browse machines and manage own reservations
# --------------------------------------------------------------------------

STATUS_FILTERS = [("", "All")] + list(Reservation.Status.choices)


def _own_reservations(user):
    return Reservation.objects.filter(farmer=user).select_related("machine")


def _filter_by_status(request, queryset):
    selected = request.GET.get("status", "")
    if selected in Reservation.Status.values:
        queryset = queryset.filter(status=selected)
    else:
        selected = ""
    return queryset, selected


@farmer_only
def machine_catalog(request):
    machines = Machine.objects.filter(cooperative_id=request.user.cooperative_id)
    return render(request, "machinery/machine_catalog.html", {"machines": machines})


@farmer_only
def my_reservations(request):
    reservations, selected = _filter_by_status(request, _own_reservations(request.user))
    return render(
        request,
        "machinery/my_reservations.html",
        {"reservations": reservations, "filters": STATUS_FILTERS, "selected": selected},
    )


@farmer_only
def reservation_create(request):
    if request.user.cooperative_id is None:
        messages.error(request, "Your account isn't linked to a cooperative yet.")
        return redirect("machinery:my_reservations")
    if request.method == "POST":
        form = ReservationForm(request.POST, farmer=request.user)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.farmer = request.user
            reservation.save()
            messages.success(
                request,
                "Reservation request sent! You'll be notified once your Cooperative Admin reviews it.",
            )
            return redirect("machinery:reservation_detail", pk=reservation.pk)
        messages.error(request, "Reservation not saved. Please fix the errors below.")
    else:
        initial = {}
        machine_id = request.GET.get("machine", "")
        if machine_id.isdigit():
            initial["machine"] = int(machine_id)
        form = ReservationForm(farmer=request.user, initial=initial)
    return render(request, "machinery/reservation_form.html", {"form": form, "is_edit": False})


@any_role
def reservation_detail(request, pk):
    if request.user.is_coop_admin:
        queryset = Reservation.objects.filter(machine__cooperative_id=request.user.cooperative_id)
    else:
        queryset = Reservation.objects.filter(farmer=request.user)
    reservation = get_object_or_404(queryset.select_related("machine", "farmer", "reviewed_by"), pk=pk)
    return render(request, "machinery/reservation_detail.html", {"reservation": reservation})


@farmer_only
def reservation_edit(request, pk):
    reservation = get_object_or_404(_own_reservations(request.user), pk=pk)
    if not reservation.is_editable:
        messages.error(request, "Only pending reservations can be edited.")
        return redirect("machinery:reservation_detail", pk=pk)
    if request.method == "POST":
        form = ReservationForm(request.POST, instance=reservation, farmer=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your reservation was updated.")
            return redirect("machinery:reservation_detail", pk=pk)
        messages.error(request, "Changes not saved. Please fix the errors below.")
    else:
        form = ReservationForm(instance=reservation, farmer=request.user)
    return render(
        request,
        "machinery/reservation_form.html",
        {"form": form, "reservation": reservation, "is_edit": True},
    )


@farmer_only
@require_POST
def reservation_cancel(request, pk):
    reservation = get_object_or_404(_own_reservations(request.user), pk=pk)
    if not reservation.is_cancellable:
        messages.error(request, "This reservation can no longer be cancelled.")
    else:
        reservation.status = Reservation.Status.CANCELLED
        reservation.save(update_fields=["status", "updated_at"])
        messages.success(request, "Your reservation was cancelled.")
    return redirect("machinery:my_reservations")


@farmer_only
@require_POST
def reservation_delete(request, pk):
    reservation = get_object_or_404(_own_reservations(request.user), pk=pk)
    if not reservation.is_deletable:
        messages.error(request, "Cancel this reservation first, then you can delete it.")
    else:
        reservation.delete()
        messages.success(request, "Reservation record deleted.")
    return redirect("machinery:my_reservations")


# --------------------------------------------------------------------------
# Cooperative Admin: review reservations of their own cooperative
# --------------------------------------------------------------------------


def _coop_reservations(user):
    return Reservation.objects.filter(machine__cooperative_id=user.cooperative_id).select_related(
        "machine", "farmer"
    )


@admin_only
def reservation_manage(request):
    reservations, selected = _filter_by_status(request, _coop_reservations(request.user))
    return render(
        request,
        "machinery/reservation_manage.html",
        {"reservations": reservations, "filters": STATUS_FILTERS, "selected": selected},
    )


@admin_only
@require_POST
def reservation_review(request, pk):
    form = ReviewForm(request.POST)
    with transaction.atomic():
        reservation = get_object_or_404(
            _coop_reservations(request.user).select_for_update(of=("self",)), pk=pk
        )
        if not form.is_valid():
            messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
        elif not reservation.is_pending:
            messages.error(request, "This reservation was already reviewed.")
        elif form.cleaned_data["decision"] == "approve":
            if reservation.has_approved_conflict():
                messages.error(
                    request,
                    "Can't approve: another approved reservation overlaps this time slot.",
                )
            else:
                _finish_review(reservation, request.user, Reservation.Status.APPROVED, form)
                messages.success(request, "Reservation approved.")
        else:
            _finish_review(reservation, request.user, Reservation.Status.REJECTED, form)
            messages.success(request, "Reservation rejected.")
    return redirect("machinery:reservation_manage")


def _finish_review(reservation, admin_user, status, form):
    reservation.status = status
    reservation.admin_remarks = (form.cleaned_data.get("remarks") or "").strip()
    reservation.reviewed_by = admin_user
    reservation.reviewed_at = timezone.now()
    reservation.save()


@admin_only
@require_POST
def reservation_complete(request, pk):
    reservation = get_object_or_404(_coop_reservations(request.user), pk=pk)
    if reservation.status != Reservation.Status.APPROVED:
        messages.error(request, "Only approved reservations can be marked as completed.")
    elif reservation.date > timezone.localdate():
        messages.error(request, "This reservation hasn't taken place yet.")
    else:
        reservation.status = Reservation.Status.COMPLETED
        reservation.save(update_fields=["status", "updated_at"])
        messages.success(request, "Reservation marked as completed.")
    return redirect("machinery:reservation_manage")
