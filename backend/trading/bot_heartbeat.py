"""Bot session heartbeat — kept separate from api.tasks to avoid circular imports."""


def touch_bot_heartbeat(session_id: int | None = None) -> None:
    """Update last_heartbeat_at on the active bot session."""
    from django.utils import timezone

    from api.models import BotSession

    qs = BotSession.objects.filter(status='running')
    if session_id:
        qs = qs.filter(pk=session_id)
    session = qs.order_by('-started_at').first()
    if session:
        session.last_heartbeat_at = timezone.now()
        session.save(update_fields=['last_heartbeat_at'])
