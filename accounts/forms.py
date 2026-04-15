from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError

from tenants.models import Business, BusinessMembership

from accounts.models import UserProfile


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Nome", required=False)
    last_name = forms.CharField(label="Apelido", required=False)
    email = forms.EmailField(label="Email", required=False, disabled=True)
    username = forms.CharField(label="Utilizador", required=False, disabled=True)

    class Meta:
        model = UserProfile
        fields = ["avatar", "phone"]
        labels = {
            "avatar": "Foto",
            "phone": "Telefone",
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
            self.fields["email"].initial = user.email
            self.fields["username"].initial = user.username
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def save(self, commit=True):
        profile = super().save(commit=commit)
        return profile


class UserPasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Password atual"
        self.fields["new_password1"].label = "Nova password"
        self.fields["new_password2"].label = "Confirmar password"
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


class TenantLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_superuser or user.groups.filter(name="SuperAdmin").exists():
            return
        memberships = BusinessMembership.objects.filter(
            user=user, is_active=True
        ).select_related("business")
        if not memberships.exists():
            raise ValidationError("Conta sem negocio associado.", code="no_business")
        has_active = False
        has_pending = False
        has_rejected = False
        for membership in memberships:
            status = membership.business.status
            if status == Business.STATUS_ACTIVE:
                has_active = True
            elif status == Business.STATUS_PENDING:
                has_pending = True
            elif status == Business.STATUS_REJECTED:
                has_rejected = True
        if has_active:
            return
        if has_pending:
            raise ValidationError(
                "Conta pendente de aprovacao. Aguarde contacto do BizControl.",
                code="pending",
            )
        if has_rejected:
            raise ValidationError(
                "Conta rejeitada. Contacte o suporte para mais informacao.",
                code="rejected",
            )
        raise ValidationError("Conta inativa.", code="inactive")


class ForgotPasswordForm(forms.Form):
    identifier = forms.CharField(
        label="Email ou utilizador",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "auth-input",
                "placeholder": "Email ou utilizador",
                "autocomplete": "username",
            }
        ),
    )
