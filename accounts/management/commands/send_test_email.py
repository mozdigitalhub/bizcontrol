from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bizcontrol.emailing import send_transactional_email


class Command(BaseCommand):
    help = "Send a transactional test email using the configured SMTP backend."

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True, help="Destination email address.")
        parser.add_argument(
            "--subject",
            default="BizControl SMTP test",
            help="Email subject.",
        )
        parser.add_argument(
            "--message",
            default="This is a test email sent by BizControl via SMTP.",
            help="Email text body.",
        )
        parser.add_argument(
            "--reply-to",
            default="",
            help="Optional reply-to address.",
        )

    def handle(self, *args, **options):
        to_email = (options.get("to") or "").strip()
        if not to_email:
            raise CommandError("You must provide --to email.")

        subject = options["subject"]
        text_message = options["message"]
        reply_to = (options.get("reply_to") or "").strip() or None
        html_message = (
            "<html><body>"
            f"<h3>{subject}</h3>"
            f"<p>{text_message}</p>"
            "<p>Sent by BizControl SMTP test command.</p>"
            "</body></html>"
        )

        ok, error = send_transactional_email(
            to_email=to_email,
            subject=subject,
            text=text_message,
            html=html_message,
            reply_to=reply_to,
        )
        if not ok:
            raise CommandError(f"Email sending failed: {error}")

        self.stdout.write(
            self.style.SUCCESS(
                "Email sent successfully. "
                f"backend={settings.EMAIL_BACKEND} host={settings.EMAIL_HOST} "
                f"from={settings.DEFAULT_FROM_EMAIL}"
            )
        )
