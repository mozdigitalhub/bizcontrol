import logging
import base64
from email.utils import formataddr, parseaddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags


logger = logging.getLogger(__name__)


def _resolve_base_sender_address():
    _, default_addr = parseaddr(getattr(settings, "DEFAULT_FROM_EMAIL", ""))
    if default_addr:
        return default_addr
    _, server_addr = parseaddr(getattr(settings, "SERVER_EMAIL", ""))
    if server_addr:
        return server_addr
    return "no-reply@bizcontrol.app"


def get_system_sender_email():
    configured = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
    if configured:
        return configured
    return formataddr(("BizControl", _resolve_base_sender_address()))


def get_tenant_sender_email(business_name):
    name = (business_name or "").strip()
    if not name:
        name = parseaddr(get_system_sender_email())[0] or "BizControl"
    return formataddr((name, _resolve_base_sender_address()))


def build_pdf_attachment(filename, content_bytes):
    return (filename, content_bytes, "application/pdf")


def send_transactional_email(
    *,
    to_email,
    subject,
    html="",
    text="",
    attachments=None,
    reply_to=None,
    from_email=None,
    fail_silently=False,
):
    if not to_email:
        return False, "Destino do email nao informado."
    if not subject:
        return False, "Assunto do email nao informado."

    html_body = html or ""
    text_body = text or strip_tags(html_body)
    if not text_body and not html_body:
        return False, "Conteudo do email nao informado."

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=(from_email or get_system_sender_email()),
        to=[to_email],
        reply_to=[reply_to] if reply_to else None,
    )
    if html_body:
        message.attach_alternative(html_body, "text/html")

    for attachment in attachments or []:
        if isinstance(attachment, tuple) and len(attachment) == 3:
            filename, content, content_type = attachment
            message.attach(filename, content, content_type)
            continue
        if isinstance(attachment, dict):
            filename = attachment.get("filename") or "attachment.bin"
            content = attachment.get("content", b"")
            content_type = attachment.get("content_type", "application/octet-stream")
            if isinstance(content, str):
                try:
                    content = base64.b64decode(content, validate=True)
                except Exception:
                    content = content.encode("utf-8")
            message.attach(filename, content, content_type)

    try:
        message.send(fail_silently=fail_silently)
    except Exception:
        logger.exception("Erro ao enviar email transacional via SMTP.")
        return False, "Nao foi possivel enviar o email."

    return True, ""
