from accounts.serializers import display_name
from match.models import MatchHistoryAction, MatchRequest, MatchRequestHistory


def actor_label(user) -> str:
    if user is None:
        return "System"
    return display_name(user)


def log_history(
    request: MatchRequest,
    action: str,
    *,
    actor=None,
    previous_value: str = "",
    new_value: str = "",
) -> MatchRequestHistory:
    actor_user = actor if actor is not None and getattr(actor, "is_authenticated", False) else None
    return MatchRequestHistory.objects.create(
        request=request,
        action=action,
        previous_value=str(previous_value or "")[:255],
        new_value=str(new_value or "")[:255],
        actor=actor_user,
    )


def log_created(request: MatchRequest, *, actor=None):
    log_history(
        request,
        MatchHistoryAction.CREATED,
        actor=actor,
        new_value=request.request_number,
    )
