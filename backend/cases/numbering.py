from __future__ import annotations

from django.db.models import Max

from cases.models import Case, CaseConversation, FollowUpStatus
from pipeline.models import PipelineStage


OPEN_STAGES = (
    PipelineStage.NEW,
    PipelineStage.QUALIFIED,
    PipelineStage.QUOTED,
    PipelineStage.NEGOTIATING,
)


def allocate_case_number() -> tuple[int, str]:
    last = Case.objects.aggregate(Max("sequence"))["sequence__max"] or 1000
    sequence = last + 1
    return sequence, f"CASE-{sequence}"


def link_conversation(case: Case, conversation, *, originating: bool = False) -> None:
    if conversation is None:
        return
    CaseConversation.objects.get_or_create(
        case=case,
        conversation=conversation,
        defaults={"is_originating": originating},
    )
    if originating or case.originating_conversation_id is None:
        case.originating_conversation = conversation
        if not case.source:
            case.source = conversation.channel
        case.save(update_fields=["originating_conversation", "source", "updated_at"])


def open_case_for_conversation(conversation) -> Case | None:
    if conversation is None:
        return None
    return (
        Case.objects.filter(conversations=conversation, stage__in=OPEN_STAGES)
        .order_by("-updated_at", "-id")
        .first()
    )


def next_pending_follow_up(case: Case):
    pending = [
        item
        for item in case.follow_ups.all()
        if item.status == FollowUpStatus.PENDING
    ]
    if not pending:
        queryset = case.follow_ups.filter(status=FollowUpStatus.PENDING)
        return queryset.order_by("due_at", "id").first()
    dated = [item for item in pending if item.due_at is not None]
    undated = [item for item in pending if item.due_at is None]
    dated.sort(key=lambda item: (item.due_at, item.pk))
    return (dated + undated)[0]
