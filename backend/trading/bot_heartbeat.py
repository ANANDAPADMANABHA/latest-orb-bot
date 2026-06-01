"""Bot session heartbeat — kept separate from api.tasks to avoid circular imports."""


def touch_bot_heartbeat(session_id: int | None = None) -> None:
    """Update last_heartbeat_at on the bot session (by id, not only status=running)."""
    from django.utils import timezone

    from api.models import BotSession

    now = timezone.now()
    if session_id:
        updated = BotSession.objects.filter(pk=session_id).update(last_heartbeat_at=now)
        if updated:
            return
    session = (
        BotSession.objects.filter(status='running').order_by('-started_at').first()
    )
    if session:
        session.last_heartbeat_at = now
        session.save(update_fields=['last_heartbeat_at'])
