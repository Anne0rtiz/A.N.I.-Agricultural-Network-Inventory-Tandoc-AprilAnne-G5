from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from machinery.models import Reservation

from .forms import CropDepositForm, RentalForm, ScanForm
from .models import CropDeposit, EquipmentRental
from .qr import qr_data_uri

admin_only = role_required(User.Role.ADMIN)
farmer_only = role_required(User.Role.FARMER)


def _coop_farmers(admin):
    return User.objects.filter(
        cooperative_id=admin.cooperative_id, role=User.Role.FARMER
    ) if admin.cooperative_id else User.objects.none()


def _get_farmer(admin, code):
    return get_object_or_404(_coop_farmers(admin), farmer_code=code.upper())


# --------------------------------------------------------------------------
# Admin: scan a QR card -> farmer workspace
# --------------------------------------------------------------------------


@admin_only
def scan(request):
    if request.method == "POST":
        form = ScanForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["farmer_code"]
            if _coop_farmers(request.user).filter(farmer_code=code).exists():
                return redirect("proxylog:farmer_workspace", code=code)
            messages.error(request, f"No farmer with ID “{code}” in your cooperative. Check the card and try again.")
        else:
            messages.error(request, "Scan a QR card or type a Farmer ID.")
    else:
        form = ScanForm()
    recent = CropDeposit.objects.filter(cooperative_id=request.user.cooperative_id).select_related("farmer")[:5]
    return render(request, "proxylog/scan.html", {"form": form, "recent": recent})


@admin_only
def farmer_workspace(request, code):
    return _render_workspace(request, _get_farmer(request.user, code))


def _render_workspace(request, farmer, rental_form=None, deposit_form=None):
    context = {
        "farmer": farmer,
        "rental_form": rental_form or RentalForm(cooperative=request.user.cooperative, farmer=farmer),
        "deposit_form": deposit_form or CropDepositForm(),
        "active_rentals": farmer.equipment_rentals.filter(status="active").select_related("machine"),
        "recent_rentals": farmer.equipment_rentals.select_related("machine")[:5],
        "recent_deposits": farmer.crop_deposits.all()[:5],
        "total_kg": farmer.crop_deposits.aggregate(t=Sum("weight_kg"))["t"] or Decimal("0"),
    }
    return render(request, "proxylog/farmer_workspace.html", context)


# ---------------------------- crop deposits --------------------------------


@admin_only
@require_POST
def deposit_create(request, code):
    farmer = _get_farmer(request.user, code)
    form = CropDepositForm(request.POST)
    if form.is_valid():
        deposit = form.save(commit=False)
        deposit.cooperative = request.user.cooperative
        deposit.farmer = farmer
        deposit.logged_by = request.user
        deposit.save()
        messages.success(
            request, f"Logged {deposit.weight_kg} kg of {deposit.get_crop_type_display()} for {farmer.display_name}."
        )
        return redirect("proxylog:farmer_workspace", code=farmer.farmer_code)
    messages.error(request, "Crop drop-off not saved. Please fix the errors below.")
    return _render_workspace(request, farmer, deposit_form=form)


def _coop_deposits(admin):
    return CropDeposit.objects.filter(cooperative_id=admin.cooperative_id).select_related("farmer")


@admin_only
def deposit_edit(request, pk):
    deposit = get_object_or_404(_coop_deposits(request.user), pk=pk)
    if request.method == "POST":
        form = CropDepositForm(request.POST, instance=deposit)
        if form.is_valid():
            form.save()
            messages.success(request, "Crop drop-off updated.")
            return redirect("proxylog:transaction_log")
        messages.error(request, "Changes not saved. Please fix the errors below.")
    else:
        form = CropDepositForm(instance=deposit)
    return render(request, "proxylog/deposit_form.html", {"form": form, "deposit": deposit})


@admin_only
@require_POST
def deposit_delete(request, pk):
    deposit = get_object_or_404(_coop_deposits(request.user), pk=pk)
    deposit.delete()
    messages.success(request, "Crop drop-off entry deleted.")
    return redirect("proxylog:transaction_log")


# ------------------------------- rentals -----------------------------------


@admin_only
@require_POST
def rental_create(request, code):
    farmer = _get_farmer(request.user, code)
    form = RentalForm(request.POST, cooperative=request.user.cooperative, farmer=farmer)
    if form.is_valid():
        rental = form.save(commit=False)
        rental.cooperative = request.user.cooperative
        rental.farmer = farmer
        rental.logged_by = request.user
        rental.reservation = form.linked_reservation
        rental.save()
        messages.success(request, f"{rental.machine.name} checked out to {farmer.display_name}.")
        return redirect("proxylog:farmer_workspace", code=farmer.farmer_code)
    messages.error(request, "Rental not saved. Please fix the errors below.")
    return _render_workspace(request, farmer, rental_form=form)


def _coop_rentals(admin):
    return EquipmentRental.objects.filter(cooperative_id=admin.cooperative_id).select_related("farmer", "machine")


@admin_only
@require_POST
def rental_return(request, pk):
    with transaction.atomic():
        rental = get_object_or_404(_coop_rentals(request.user).select_for_update(of=("self",)), pk=pk)
        if not rental.is_active:
            messages.error(request, "This rental was already returned.")
        else:
            rental.status = EquipmentRental.Status.RETURNED
            rental.returned_at = timezone.now()
            rental.save(update_fields=["status", "returned_at"])
            if rental.reservation_id and rental.reservation.status == Reservation.Status.APPROVED:
                rental.reservation.status = Reservation.Status.COMPLETED
                rental.reservation.save(update_fields=["status", "updated_at"])
            messages.success(request, f"{rental.machine.name} returned after {rental.hours_used} hrs.")
    return redirect("proxylog:farmer_workspace", code=rental.farmer.farmer_code)


@admin_only
@require_POST
def rental_delete(request, pk):
    rental = get_object_or_404(_coop_rentals(request.user), pk=pk)
    rental.delete()
    messages.success(request, "Rental entry deleted.")
    return redirect("proxylog:transaction_log")


# ----------------------------- transaction log -----------------------------


@admin_only
def transaction_log(request):
    kind = request.GET.get("type", "")
    q = request.GET.get("q", "").strip()
    rentals, deposits = _coop_rentals(request.user), _coop_deposits(request.user)
    if q:
        match = (Q(farmer__farmer_code__icontains=q) | Q(farmer__first_name__icontains=q)
                 | Q(farmer__last_name__icontains=q))
        rentals, deposits = rentals.filter(match), deposits.filter(match)
    if kind == "rentals":
        deposits = deposits.none()
    elif kind == "deposits":
        rentals = rentals.none()
    else:
        kind = ""
    totals = (
        _coop_deposits(request.user).values("crop_type").annotate(total=Sum("weight_kg")).order_by("-total")
    )
    labels = dict(CropDeposit.CropType.choices)
    yields = [(labels[t["crop_type"]], t["total"]) for t in totals]
    return render(request, "proxylog/transaction_log.html", {
        "rentals": rentals[:100], "deposits": deposits[:100], "kind": kind, "q": q, "yields": yields,
    })


# ---------------------------- QR cards -------------------------------------


@admin_only
def card_list(request):
    farmers = _coop_farmers(request.user).order_by("last_name", "first_name")
    return render(request, "proxylog/card_list.html", {"farmers": farmers})


@admin_only
def card_print(request, code):
    farmer = _get_farmer(request.user, code)
    return render(request, "proxylog/card.html", {"farmer": farmer, "qr": qr_data_uri(farmer.farmer_code),
                                                  "is_admin_view": True})


@farmer_only
def my_qr(request):
    return render(request, "proxylog/card.html", {"farmer": request.user,
                                                  "qr": qr_data_uri(request.user.farmer_code)})


@farmer_only
def my_contributions(request):
    me = request.user
    return render(request, "proxylog/my_contributions.html", {
        "deposits": me.crop_deposits.all(),
        "rentals": me.equipment_rentals.select_related("machine"),
        "total_kg": me.crop_deposits.aggregate(t=Sum("weight_kg"))["t"] or Decimal("0"),
    })
