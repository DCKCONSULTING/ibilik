from django.db import migrations
from django.db.models import Max


def copy_opportunities_to_cases(apps, schema_editor):
    Opportunity = apps.get_model("pipeline", "Opportunity")
    Case = apps.get_model("cases", "Case")
    CaseConversation = apps.get_model("cases", "CaseConversation")
    CaseActivity = apps.get_model("cases", "CaseActivity")
    Message = apps.get_model("crm", "Message")

    last = Case.objects.aggregate(Max("sequence"))["sequence__max"] or 1000
    for opportunity in Opportunity.objects.select_related("conversation").order_by("id"):
        external_key = opportunity.external_key or f"migrated-opportunity-{opportunity.pk}"
        if Case.objects.filter(external_key=external_key).exists():
            continue
        last += 1
        original_request = opportunity.description or opportunity.title
        originating_message_id = None
        source = ""
        if opportunity.conversation_id:
            source = opportunity.conversation.channel or ""
            inbound = (
                Message.objects.filter(conversation_id=opportunity.conversation_id, direction="inbound")
                .order_by("created_at", "id")
                .first()
            )
            if inbound is not None:
                original_request = inbound.content or original_request
                originating_message_id = inbound.pk
        closed_at = opportunity.updated_at if opportunity.stage in {"won", "lost"} else None
        case = Case.objects.create(
            sequence=last,
            case_number=f"CASE-{last}",
            customer_id=opportunity.customer_id,
            property_id=opportunity.property_id,
            originating_conversation_id=opportunity.conversation_id,
            originating_message_id=originating_message_id,
            title=opportunity.title,
            description=opportunity.description,
            original_request=original_request,
            source=source,
            stage=opportunity.stage,
            value=opportunity.value,
            quote_notes=opportunity.quote_notes,
            staff_notes=opportunity.staff_notes,
            finance_status=opportunity.finance_status,
            assigned_to_id=opportunity.assigned_to_id,
            created_by_id=opportunity.created_by_id,
            quoted_at=opportunity.quoted_at,
            approved_at=opportunity.approved_at,
            finance_moved_at=opportunity.finance_moved_at,
            closed_at=closed_at,
            external_key=external_key,
        )
        Case.objects.filter(pk=case.pk).update(created_at=opportunity.created_at, updated_at=opportunity.updated_at)
        if opportunity.conversation_id:
            CaseConversation.objects.get_or_create(
                case_id=case.pk,
                conversation_id=opportunity.conversation_id,
                defaults={"is_originating": True},
            )
        CaseActivity.objects.create(
            case_id=case.pk,
            event_type="created",
            message=f"Case created. Source: {source or 'unspecified'}.",
            actor_id=opportunity.created_by_id,
        )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0001_initial"),
        ("pipeline", "0003_opportunity_staff_notes"),
        ("crm", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(copy_opportunities_to_cases, noop_reverse),
    ]
