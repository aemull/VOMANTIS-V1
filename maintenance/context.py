from .access import is_manager, visible_tickets


def navigation(request):
    if not request.user.is_authenticated:
        return {}
    manager = is_manager(request.user)
    return {'is_manager': manager, 'review_count': visible_tickets(request.user).filter(status='Review').count(),
            'role_name': 'Manager' if manager else 'Teknisi'}
