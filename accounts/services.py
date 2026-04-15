from django.urls import reverse
from django.utils import timezone
from django.template.loader import render_to_string

from accounts.models import UserProfile
from accounts.passwords import generate_temp_password
from bizcontrol.emailing import send_transactional_email


def reset_password_and_send_email(*, user, request=None):
    if not user or not user.email:
        return False, "Utilizador sem email configurado."

    temp_password = generate_temp_password()
    user.set_password(temp_password)
    user.save(update_fields=["password"])

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.must_change_password = True
    profile.temp_password_set_at = timezone.now()
    profile.save(update_fields=["must_change_password", "temp_password_set_at"])

    login_url = ""
    if request:
        login_url = request.build_absolute_uri(reverse("login"))

    subject = "BizControl - Nova palavra-passe temporaria"
    context = {
        "user": user,
        "temp_password": temp_password,
        "login_url": login_url,
    }
    html = render_to_string("emails/password_reset_temp.html", context)
    text = render_to_string("emails/password_reset_temp.txt", context)
    ok, error = send_transactional_email(
        to_email=user.email,
        subject=subject,
        html=html,
        text=text,
        fail_silently=False,
    )
    return ok, error or ""
