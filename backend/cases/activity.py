from accounts.serializers import display_name
from cases.models import ActivityEvent, Case, CaseActivity


def actor_name(user) -> str:
    if user is None:
        return "System"
    return display_name(user)


def log_activity(case: Case, event_type: str, message: str, *, actor=None) -> CaseActivity:
    actor_user = actor if actor is not None and getattr(actor, "is_authenticated", False) else None
    return CaseActivity.objects.create(
        case=case,
        event_type=event_type,
        message=message[:500],
        actor=actor_user,
    )


def log_created(case: Case, *, actor=None):
    source = case.source or "unspecified"
    log_activity(case, ActivityEvent.CREATED, f"Case created. Source: {source}.", actor=actor)


def log_assigned(case: Case, *, actor=None, previous=None):
    name = actor_name(case.assigned_to)
    if case.assigned_to is None:
        message = "Staff unassigned."
    elif previous is None:
        message = f"Assigned to {name}."
    else:
        message = f"Assigned to {name}."
    log_activity(case, ActivityEvent.ASSIGNED, message, actor=actor)
