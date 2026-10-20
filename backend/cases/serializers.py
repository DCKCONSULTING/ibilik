from __future__ import annotations

from decimal import Decimal

from accounts.serializers import display_name
from cases.models import Case, CaseActivity, CaseFollowUp, FollowUpStatus, FollowUpType
from cases.numbering import next_pending_follow_up
from cases.workflow import allowed_actions
from crm.serializers import serialize_identity, serialize_message
from pipeline.models import PIPELINE_STAGES, FinanceStatus, PipelineStage


CHANNEL_LABELS = {
    "website": "Website",
    "whatsapp": "WhatsApp",
    "facebook": "Facebook Messenger",
}


def isoformat(value):
    return value.isoformat() if value else None


def _serialize_location_ref(location) -> dict | None:
    if location is None:
        return None
    return {
        "id": location.pk,
        "name": location.name,
        "code": location.code,
        "type": location.location_type,
        "type_label": location.get_location_type_display(),
    }


def format_value(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value:.2f}"


def stage_label(stage: str) -> str:
    try:
        return PipelineStage(stage).label
    except ValueError:
        return stage


def finance_status_label(status: str) -> str:
    try:
        return FinanceStatus(status).label
    except ValueError:
        return status


def serialize_user_summary(user) -> dict | None:
    if user is None:
        return None
    name = display_name(user)
    return {
        "id": user.pk,
        "username": user.username,
        "name": name,
        "display_name": name,
    }


def serialize_follow_up(follow_up: CaseFollowUp, *, include_context: bool = False) -> dict:
    status = follow_up.status
    if follow_up.is_overdue():
        status = "overdue"
    payload = {
        "id": follow_up.pk,
        "case_id": follow_up.case_id,
        "type": follow_up.follow_up_type,
        "type_label": FollowUpType(follow_up.follow_up_type).label if follow_up.follow_up_type in FollowUpType.values else follow_up.follow_up_type,
        "title": follow_up.title,
        "description": follow_up.description,
        "status": status,
        "status_label": "Overdue" if status == "overdue" else follow_up.get_status_display(),
        "assigned_to": serialize_user_summary(follow_up.assigned_to),
        "due_at": isoformat(follow_up.due_at),
        "completed_at": isoformat(follow_up.completed_at),
        "created_at": isoformat(follow_up.created_at),
        "updated_at": isoformat(follow_up.updated_at),
    }
    if include_context:
        case = follow_up.case
        customer = case.customer
        property_obj = case.property
        source = case.source
        payload["case"] = {
            "id": case.pk,
            "case_number": case.case_number,
            "title": case.title,
            "stage": case.stage,
            "stage_label": stage_label(case.stage),
            "source": source,
            "source_label": CHANNEL_LABELS.get(source, source) if source else None,
        }
        payload["customer"] = {
            "id": customer.pk,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "status": customer.status,
        }
        payload["property"] = None if property_obj is None else {"id": property_obj.pk, "name": property_obj.name}
        payload["created_by"] = serialize_user_summary(follow_up.created_by)
    return payload


def serialize_activity(activity: CaseActivity) -> dict:
    return {
        "id": activity.pk,
        "event_type": activity.event_type,
        "message": activity.message,
        "actor": serialize_user_summary(activity.actor),
        "created_at": isoformat(activity.created_at),
    }


def serialize_next_follow_up(case: Case) -> dict | None:
    follow_up = next_pending_follow_up(case)
    if follow_up is None:
        return None
    return serialize_follow_up(follow_up)


def case_messages(case: Case):
    conversation_ids = list(case.conversations.values_list("id", flat=True))
    if case.originating_conversation_id and case.originating_conversation_id not in conversation_ids:
        conversation_ids.append(case.originating_conversation_id)
    if not conversation_ids:
        return []
    from crm.models import Message

    return list(
        Message.objects.filter(conversation_id__in=conversation_ids)
        .select_related("created_by", "conversation")
        .order_by("created_at", "id")[:80]
    )


def serialize_case(case: Case, *, include_detail: bool = False) -> dict:
    customer = case.customer
    property_obj = case.property
    conversation = case.originating_conversation
    assigned = serialize_user_summary(case.assigned_to)
    source = case.source or (conversation.channel if conversation is not None else None)
    request_text = case.original_request or case.description
    payload = {
        "id": case.pk,
        "case_number": case.case_number,
        "title": case.title,
        "description": case.description,
        "request": request_text,
        "request_preview": request_text,
        "original_request": case.original_request,
        "stage": case.stage,
        "stage_label": stage_label(case.stage),
        "value": format_value(case.value),
        "quote_notes": case.quote_notes,
        "staff_notes": case.staff_notes,
        "finance_status": case.finance_status,
        "finance_status_label": finance_status_label(case.finance_status),
        "source": source,
        "source_label": CHANNEL_LABELS.get(source, source),
        "allowed_actions": allowed_actions(case),
        "customer": {
            "id": customer.pk,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "status": customer.status,
        },
        "property": None
        if property_obj is None
        else {
            "id": property_obj.pk,
            "name": property_obj.name,
        },
        "location": _serialize_location_ref(getattr(case, "location", None)),
        "assigned_to": assigned,
        "assigned_user": assigned,
        "assigned_staff": assigned,
        "created_by": serialize_user_summary(case.created_by),
        "conversation_id": conversation.pk if conversation is not None else None,
        "conversation": None
        if conversation is None
        else {
            "id": conversation.pk,
            "channel": conversation.channel,
            "channel_label": CHANNEL_LABELS.get(conversation.channel, conversation.channel),
            "subject": conversation.subject,
        },
        "next_follow_up": serialize_next_follow_up(case),
        "quoted_at": isoformat(case.quoted_at),
        "approved_at": isoformat(case.approved_at),
        "finance_moved_at": isoformat(case.finance_moved_at),
        "check_in": isoformat(case.check_in),
        "check_out": isoformat(case.check_out),
        "closed_at": isoformat(case.closed_at),
        "created_at": isoformat(case.created_at),
        "updated_at": isoformat(case.updated_at),
    }
    if include_detail:
        payload["customer"]["identities"] = [serialize_identity(item) for item in customer.identities.all()]
        payload["follow_ups"] = [serialize_follow_up(item) for item in case.follow_ups.select_related("assigned_to")]
        payload["activities"] = [serialize_activity(item) for item in case.activities.select_related("actor")[:50]]
        messages = case_messages(case)
        if conversation is not None:
            payload["conversation"]["messages"] = [
                serialize_message(item) for item in messages if item.conversation_id == conversation.pk
            ]
        payload["messages"] = [serialize_message(item) for item in messages]
        payload["conversations"] = [
            {
                "id": item.pk,
                "channel": item.channel,
                "channel_label": CHANNEL_LABELS.get(item.channel, item.channel),
                "subject": item.subject,
            }
            for item in case.conversations.all()
        ]
    return payload


def serialize_case_summary(case: Case) -> dict:
    return {
        "id": case.pk,
        "case_number": case.case_number,
        "title": case.title,
        "stage": case.stage,
        "stage_label": stage_label(case.stage),
        "updated_at": isoformat(case.updated_at),
    }


def serialize_pipeline_stages() -> list[dict]:
    return [{"id": item["id"], "label": item["label"], "order": item["order"]} for item in PIPELINE_STAGES]


def serialize_follow_up_types() -> list[dict]:
    return [{"id": value, "label": label} for value, label in FollowUpType.choices]


def serialize_follow_up_sources() -> list[dict]:
    return [{"id": key, "label": label} for key, label in CHANNEL_LABELS.items()]
