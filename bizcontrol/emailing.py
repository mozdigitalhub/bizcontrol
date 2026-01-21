import base64
import logging

import requests
from django.conf import settings


logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def build_pdf_attachment(filename, content_bytes):
    return {
        "filename": filename,
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "content_type": "application/pdf",
    }


def send_resend_email(*, to_email, subject, html, attachments=None, reply_to=None):
    api_key = settings.RESEND_API_KEY
    if not api_key:
        return False, "Envio de email nao configurado."

    from_email = settings.RESEND_FROM_EMAIL
    from_name = settings.RESEND_FROM_NAME or "BizControl"
    payload = {
        "from": f"{from_name} <{from_email}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    if attachments:
        payload["attachments"] = attachments

    try:
        response = requests.post(
            RESEND_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20,
        )
    except requests.RequestException:
        logger.exception("Erro ao enviar email via Resend.")
        return False, "Nao foi possivel enviar o email."

    if 200 <= response.status_code < 300:
        return True, ""

    logger.error("Erro Resend (%s): %s", response.status_code, response.text)
    return False, "Nao foi possivel enviar o email."
