from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.integrations.twilio_client import TwilioWhatsAppClient
from app.integrations.twilio_whatsapp import normalize_twilio_webhook
from app.services.conversation_service import get_or_create_active_conversation, touch_conversation
from app.services.document_extraction_service import DocumentExtractionService
from app.services.document_service import (
    create_document_from_message,
    update_document_extracted_text,
    update_document_storage_path,
    update_document_understanding,
)
from app.workflows.guided_journey.context import build_guided_journey_state
from app.workflows.guided_journey.graph import guided_journey_graph
from app.services.document_understanding_service import DocumentUnderstandingService
from app.services.knowledge_service import KnowledgeService
from app.services.media_service import download_media_for_document
from app.services.message_service import (
    create_inbound_message,
    create_outbound_message,
    get_recent_messages_for_conversation,
)
from app.services.reply_service import build_document_understanding_reply
from app.services.user_service import get_or_create_user_by_phone_number
from app.services.workflow_service import (
    get_active_workflow_for_conversation,
    sync_workflow_from_guided_journey_result,
    sync_workflow_from_intake_result,
)
from app.workflows.intake_router.context import build_intake_router_state
from app.workflows.intake_router.graph import intake_router_graph

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/webhooks/twilio/whatsapp")
async def twilio_whatsapp_webhook(request: Request, session: Session = Depends(get_db_session)) -> dict:
    form = await request.form()
    normalized = normalize_twilio_webhook(form)

    user = get_or_create_user_by_phone_number(
        session,
        phone_number=normalized.phone_number,
        display_name=normalized.profile_name,
    )
    conversation = get_or_create_active_conversation(session, user.id)
    message = create_inbound_message(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        inbound_message=normalized,
    )
    touch_conversation(session, conversation)

    document = None
    if normalized.message_type in {"image", "document"}:
        document = create_document_from_message(
            session,
            user_id=user.id,
            conversation_id=conversation.id,
            source_message=message,
        )
        if normalized.media_url:
            storage_path = download_media_for_document(document, normalized.media_url)
            document = update_document_storage_path(
                session,
                document,
                file_storage_path=storage_path,
                processing_status="stored",
            )
            extracted_text = DocumentExtractionService().extract_text(document)
            document = update_document_extracted_text(
                session,
                document,
                extracted_text=extracted_text,
                processing_status="extracted",
            )
            understanding_language = result.get("inferred_language") if 'result' in locals() else user.preferred_language or "nl"
            understanding = DocumentUnderstandingService().understand(document, language=understanding_language)
            if understanding is not None:
                document = update_document_understanding(
                    session,
                    document,
                    result=understanding,
                    processing_status="understood",
                )

    active_workflow = get_active_workflow_for_conversation(session, conversation.id)
    recent_messages = get_recent_messages_for_conversation(
        session,
        conversation_id=conversation.id,
        limit=5,
    )

    state = build_intake_router_state(
        user=user,
        conversation=conversation,
        message=message,
        recent_messages=recent_messages,
        active_workflow=active_workflow,
        is_new_user=False,
        is_new_conversation=False,
    )
    result = intake_router_graph.invoke(state)

    guided_journey_key = None
    if active_workflow is not None and active_workflow.workflow_type == "guided_journey":
        guided_journey_key = (active_workflow.state_json or {}).get("journey_key")
    elif result.get("transition_to_workflow") == "guided_journey" and result.get("guided_journey_key"):
        guided_journey_key = result.get("guided_journey_key")
    elif document and document.journey_candidate:
        guided_journey_key = document.journey_candidate

    if guided_journey_key:
        guided_active_workflow = active_workflow
        guided_state = build_guided_journey_state(
            journey_key=guided_journey_key,
            user=user,
            conversation=conversation,
            message=message,
            recent_messages=recent_messages,
            active_workflow=guided_active_workflow,
            inferred_language=result.get("inferred_language"),
            situation_summary=result.get("situation_summary"),
        )
        guided_result = guided_journey_graph.invoke(guided_state)
        synced_workflow = sync_workflow_from_guided_journey_result(
            session,
            user_id=user.id,
            conversation_id=conversation.id,
            active_workflow=guided_active_workflow,
            state=guided_result,
        )
        reply_language = guided_result.get("inferred_language") or user.preferred_language or "nl"
        selected_knowledge = KnowledgeService().select_for_journey(
            journey_key=guided_journey_key,
            user_message=normalized.text,
            document_summary=(document.summary if document else None),
            document_journey_candidate=(document.journey_candidate if document else None),
        )
        document_reply = build_document_understanding_reply(
            document,
            language=reply_language,
            selected_knowledge=selected_knowledge,
        ) if document else None
        reply_text = guided_result.get("reply_text") or document_reply or "Hoi, ik heb je bericht goed ontvangen."
        result["transition_to_workflow"] = "guided_journey"
    else:
        synced_workflow = sync_workflow_from_intake_result(
            session,
            user_id=user.id,
            conversation_id=conversation.id,
            active_workflow=active_workflow,
            state=result,
        )
        reply_language = result.get("inferred_language") or user.preferred_language or "nl"
        selected_knowledge = None
        document_reply = build_document_understanding_reply(
            document,
            language=reply_language,
            selected_knowledge=selected_knowledge,
        ) if document else None
        reply_text = document_reply or result.get("reply_text") or "Hoi, ik heb je bericht goed ontvangen."

    outbound_message_sid = TwilioWhatsAppClient().send_whatsapp_message(
        to_phone_number=normalized.phone_number,
        body=reply_text,
    )
    outbound_message = create_outbound_message(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        content_text=reply_text,
        whatsapp_message_id=outbound_message_sid,
    )

    return {
        "status": "received",
        "user_id": user.id,
        "conversation_id": conversation.id,
        "message_id": message.id,
        "document_id": document.id if document else None,
        "document_storage_path": document.file_storage_path if document else None,
        "document_processing_status": document.processing_status if document else None,
        "document_type": document.document_type if document else None,
        "document_journey_candidate": document.journey_candidate if document else None,
        "document_summary_preview": (document.summary[:200] if document and document.summary else None),
        "document_extracted_text_preview": (document.extracted_text[:200] if document and document.extracted_text else None),
        "provider": normalized.provider,
        "channel": normalized.channel,
        "phone_number": normalized.phone_number,
        "message_type": normalized.message_type,
        "text": normalized.text,
        "media_url": normalized.media_url,
        "media_content_type": normalized.media_content_type,
        "num_media": normalized.num_media,
        "external_message_id": normalized.external_message_id,
        "graph_workflow_type_candidate": result.get("workflow_type_candidate"),
        "graph_transition_to_workflow": result.get("transition_to_workflow"),
        "graph_next_expected_input": result.get("next_expected_input"),
        "workflow_id": synced_workflow.id,
        "workflow_type": synced_workflow.workflow_type,
        "workflow_step": synced_workflow.current_step,
        "outbound_message_sid": outbound_message_sid,
        "outbound_message_id": outbound_message.id,
    }
