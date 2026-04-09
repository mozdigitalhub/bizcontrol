from django.core import mail
from django.test import TestCase, override_settings

from bizcontrol.emailing import (
    build_pdf_attachment,
    get_tenant_sender_email,
    send_transactional_email,
)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="BizControl <no-reply@bizcontrol.app>",
)
class TransactionalEmailServiceTests(TestCase):
    def test_send_html_email_with_attachment_and_reply_to(self):
        attachment = build_pdf_attachment("test.pdf", b"pdf-content")
        ok, error = send_transactional_email(
            to_email="client@example.com",
            subject="Teste SMTP",
            text="Mensagem de teste",
            html="<p>Mensagem de teste</p>",
            attachments=[attachment],
            reply_to="support@bizcontrol.app",
        )

        self.assertTrue(ok)
        self.assertEqual(error, "")
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.subject, "Teste SMTP")
        self.assertEqual(sent.to, ["client@example.com"])
        self.assertEqual(sent.reply_to, ["support@bizcontrol.app"])
        self.assertEqual(len(sent.alternatives), 1)
        self.assertEqual(len(sent.attachments), 1)

    def test_requires_recipient_and_subject(self):
        ok, error = send_transactional_email(
            to_email="",
            subject="",
            text="msg",
        )
        self.assertFalse(ok)
        self.assertIn("Destino do email", error)

    def test_tenant_sender_name_uses_business_name(self):
        sender = get_tenant_sender_email("Ferragem Maputo")
        ok, error = send_transactional_email(
            to_email="client@example.com",
            subject="Documento",
            text="Teste",
            from_email=sender,
        )
        self.assertTrue(ok)
        self.assertEqual(error, "")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "Ferragem Maputo <no-reply@bizcontrol.app>")
