from email.utils import parseaddr

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from bizcontrol.emailing import send_transactional_email
from tenants.models import DocumentSequence, TenantEmailLog


def _log_email(*, business, email_type, recipient, subject, status, error_message="", sent_by=None):
    actor = sent_by if getattr(sent_by, "is_authenticated", False) else None
    TenantEmailLog.objects.create(
        business=business,
        email_type=email_type,
        recipient=recipient,
        subject=subject,
        status=status,
        error_message=error_message or "",
        sent_by=actor,
    )


def _email_brand_context():
    support_name, support_email = parseaddr(getattr(settings, "DEFAULT_FROM_EMAIL", ""))
    support_contact = (
        support_email
        or getattr(settings, "SERVER_EMAIL", "")
        or "suporte@bizcontrol.app"
    )
    return {
        "brand_logo_url": getattr(settings, "EMAIL_BRAND_LOGO_URL", ""),
        "support_contact": support_contact,
        "support_name": support_name or "BizControl",
    }


def send_pending_email(*, business, owner, request=None):
    subject = "Registo recebido - BizControl"
    brand_context = _email_brand_context()
    html = render_to_string(
        "emails/tenant_pending.html",
        {
            "business": business,
            "owner": owner,
            **brand_context,
        },
    )
    ok, error = send_transactional_email(to_email=owner.email, subject=subject, html=html)
    _log_email(
        business=business,
        email_type=TenantEmailLog.TYPE_PENDING,
        recipient=owner.email,
        subject=subject,
        status=TenantEmailLog.STATUS_SENT if ok else TenantEmailLog.STATUS_FAILED,
        error_message=error,
        sent_by=getattr(request, "user", None),
    )
    return ok, error


def send_approved_email(*, business, owner, temp_password, login_url, approved_by=None):
    subject = "Conta aprovada - BizControl"
    brand_context = _email_brand_context()
    html = render_to_string(
        "emails/tenant_approved.html",
        {
            "business": business,
            "owner": owner,
            "temp_password": temp_password,
            "login_url": login_url,
            **brand_context,
        },
    )
    ok, error = send_transactional_email(to_email=owner.email, subject=subject, html=html)
    _log_email(
        business=business,
        email_type=TenantEmailLog.TYPE_APPROVED,
        recipient=owner.email,
        subject=subject,
        status=TenantEmailLog.STATUS_SENT if ok else TenantEmailLog.STATUS_FAILED,
        error_message=error,
        sent_by=approved_by,
    )
    return ok, error


def send_rejected_email(*, business, owner, rejected_by=None):
    subject = "Registo nao aprovado - BizControl"
    brand_context = _email_brand_context()
    html = render_to_string(
        "emails/tenant_rejected.html",
        {
            "business": business,
            "owner": owner,
            **brand_context,
        },
    )
    ok, error = send_transactional_email(to_email=owner.email, subject=subject, html=html)
    _log_email(
        business=business,
        email_type=TenantEmailLog.TYPE_REJECTED,
        recipient=owner.email,
        subject=subject,
        status=TenantEmailLog.STATUS_SENT if ok else TenantEmailLog.STATUS_FAILED,
        error_message=error,
        sent_by=rejected_by,
    )
    return ok, error


def generate_document_code(*, business, doc_type, prefix, date=None):
    seq_date = date or timezone.localdate()
    with transaction.atomic():
        seq = (
            DocumentSequence.objects.select_for_update()
            .filter(business=business, doc_type=doc_type, seq_date=seq_date)
            .first()
        )
        if not seq:
            seq = DocumentSequence.objects.create(
                business=business, doc_type=doc_type, seq_date=seq_date, current_value=0
            )
        seq.current_value += 1
        seq.save(update_fields=["current_value"])
        seq_value = seq.current_value
    return f"{prefix}-{seq_date.strftime('%y%m%d')}-{business.id}-{seq_value:03d}"
