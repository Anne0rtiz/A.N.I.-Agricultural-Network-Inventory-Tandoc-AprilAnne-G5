from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import MachineForm
from .models import Machine

admin_only = role_required(User.Role.ADMIN)


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
