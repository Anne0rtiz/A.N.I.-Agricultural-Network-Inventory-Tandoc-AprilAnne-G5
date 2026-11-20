from .models import Reservation


def pending_reservations(request):
    """Adds the count of pending requests to every page a Cooperative Admin sees."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and user.is_coop_admin and user.cooperative_id):
        return {}
    count = Reservation.objects.filter(
        machine__cooperative_id=user.cooperative_id, status=Reservation.Status.PENDING
    ).count()
    return {"pending_count": count}
