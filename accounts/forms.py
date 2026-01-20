from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm

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
