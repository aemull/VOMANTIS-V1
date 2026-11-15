from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q


def is_manager(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name='Manager').exists())


def technicians():
    from django.contrib.auth import get_user_model
    return get_user_model().objects.filter(is_active=True, groups__name='Teknisi').distinct()


def manager_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_manager(request.user):
            raise PermissionDenied('Halaman ini khusus Manager.')
        return view(request, *args, **kwargs)
    return wrapped


def visible_tickets(user):
    from .models import WorkOrder
    qs = WorkOrder.objects.select_related('asset', 'assigned_to')
    return qs if is_manager(user) else qs.filter(assigned_to=user)
