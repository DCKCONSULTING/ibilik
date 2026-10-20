from __future__ import annotations

from django.utils import timezone

from cases.activity import log_activity
from cases.models import ActivityEvent, Case
from cases.services import CaseError, _parse_value
from pipeline.models import FinanceStatus, PipelineStage


ACTION_QUALIFY = "qualify"
ACTION_QUOTE = "quote"
ACTION_APPROVE = "approve"
ACTION_MOVE_TO_FINANCE = "move_to_finance"
ACTION_REOPEN = "reopen"

WORKFLOW_ACTIONS = (
    ACTION_QUALIFY,
    ACTION_QUOTE,
    ACTION_APPROVE,
    ACTION_MOVE_TO_FINANCE,
    ACTION_REOPEN,
)


def allowed_actions(case: Case) -> list[str]:
    actions: list[str] = []
    if case.stage == PipelineStage.NEW:
        actions.append(ACTION_QUALIFY)
    if case.stage in {PipelineStage.NEW, PipelineStage.QUALIFIED}:
        actions.append(ACTION_QUOTE)
    if case.stage in {PipelineStage.QUOTED, PipelineStage.NEGOTIATING}:
        actions.append(ACTION_APPROVE)
    if case.stage in {PipelineStage.NEGOTIATING, PipelineStage.WON}:
        if case.finance_status != FinanceStatus.SENT:
            actions.append(ACTION_MOVE_TO_FINANCE)
    if case.stage == PipelineStage.LOST:
        actions.append(ACTION_REOPEN)
    return actions


def perform_workflow_action(case: Case, payload: dict, *, actor=None) -> Case:
    action = str(payload.get("action") or "").strip().lower()
    if action not in WORKFLOW_ACTIONS:
        raise CaseError("Unknown workflow action.", code="invalid_action")
    if action not in allowed_actions(case):
        raise CaseError(
            f"The '{action}' action is not allowed from the {case.get_stage_display()} stage.",
            code="invalid_transition",
        )

    previous = case.stage
    now = timezone.now()
    if action == ACTION_QUALIFY:
        case.stage = PipelineStage.QUALIFIED
        log_activity(case, ActivityEvent.STAGE_CHANGED, "Moved from New → Qualified.", actor=actor)
    elif action == ACTION_QUOTE:
        if "value" in payload:
            case.value = _parse_value(payload.get("value"))
        if "notes" in payload or "quote_notes" in payload:
            case.quote_notes = str(payload.get("notes") or payload.get("quote_notes") or "")
        case.stage = PipelineStage.QUOTED
        case.quoted_at = now
        log_activity(case, ActivityEvent.QUOTE_CREATED, "Quote created.", actor=actor)
        if previous != case.stage:
            log_activity(case, ActivityEvent.STAGE_CHANGED, f"Moved from {PipelineStage(previous).label} → Quoted.", actor=actor)
    elif action == ACTION_APPROVE:
        case.approved_at = now
        case.stage = PipelineStage.WON if case.stage == PipelineStage.NEGOTIATING else PipelineStage.NEGOTIATING
        log_activity(case, ActivityEvent.APPROVED, "Approval performed.", actor=actor)
        log_activity(
            case,
            ActivityEvent.STAGE_CHANGED,
            f"Moved from {PipelineStage(previous).label} → {PipelineStage(case.stage).label}.",
            actor=actor,
        )
        if case.stage == PipelineStage.WON:
            case.closed_at = now
            log_activity(case, ActivityEvent.CLOSED, "Case closed.", actor=actor)
    elif action == ACTION_MOVE_TO_FINANCE:
        case.finance_status = FinanceStatus.SENT
        case.finance_moved_at = now
        log_activity(case, ActivityEvent.MOVED_TO_FINANCE, "Moved to finance.", actor=actor)
    elif action == ACTION_REOPEN:
        case.stage = PipelineStage.NEW
        case.finance_status = FinanceStatus.NONE
        case.closed_at = None
        log_activity(case, ActivityEvent.REOPENED, "Case reopened.", actor=actor)

    case.save()
    from quotes.services import sync_quote_after_workflow

    sync_quote_after_workflow(case, action, actor=actor)
    return case
