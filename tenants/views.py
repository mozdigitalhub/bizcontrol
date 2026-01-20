from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ParseError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from accounts.forms import UserPasswordForm, UserProfileForm
from accounts.models import UserProfile
from tenants.decorators import _is_owner, business_required, owner_required
from tenants.forms import (
    BusinessProfileForm,
    BusinessSettingsForm,
    TenantBankAccountForm,
    TenantMobileWalletForm,
)
from tenants.models import Business, BusinessMembership, TenantBankAccount, TenantMobileWallet
from tenants.serializers import TenantRegisterSerializer


@login_required
def select_business(request):
    is_superuser = request.user.is_superuser
    memberships = None
    businesses = None
    if is_superuser:
        businesses = Business.objects.order_by("name")
    else:
        memberships = (
            BusinessMembership.objects.filter(user=request.user, is_active=True)
            .select_related("business")
            .order_by("business__name")
        )
    if request.method == "POST":
        business_id = request.POST.get("business_id")
        business = None
        if is_superuser:
            business = businesses.filter(id=business_id).first() if businesses else None
        else:
            membership = memberships.filter(business_id=business_id).first()
            business = membership.business if membership else None
        if not business:
            messages.error(request, "Negocio invalido.")
        else:
            request.session["business_id"] = business.id
            next_url = request.GET.get("next") or "reports:dashboard"
            return redirect(next_url)
    return render(
        request,
        "tenants/select_business.html",
        {"memberships": memberships, "businesses": businesses, "is_superuser": is_superuser},
    )


@login_required
@business_required
def business_settings(request):
    business = request.business
    is_owner = _is_owner(request)
    active_tab = request.GET.get("tab", "tenant")
    wallets = TenantMobileWallet.objects.filter(business=business).order_by("-is_active", "id")
    banks = TenantBankAccount.objects.filter(business=business).order_by("-is_active", "id")

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action", "tenant_profile")
        if action == "tenant_profile":
            profile_form = BusinessProfileForm(
                request.POST,
                request.FILES,
                instance=business,
                can_edit_legal=is_owner,
            )
            settings_form = BusinessSettingsForm(
                instance=business, can_edit_settings=is_owner
            )
            user_form = UserProfileForm(instance=profile, user=request.user)
            password_form = UserPasswordForm(user=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Perfil do negocio atualizado.")
                return redirect(f"{reverse('tenants:settings')}?tab=tenant")
            active_tab = "tenant"
        elif action == "system_settings":
            profile_form = BusinessProfileForm(
                instance=business, can_edit_legal=is_owner
            )
            settings_form = BusinessSettingsForm(
                request.POST, instance=business, can_edit_settings=is_owner
            )
            user_form = UserProfileForm(instance=profile, user=request.user)
            password_form = UserPasswordForm(user=request.user)
            if not is_owner:
                messages.error(request, "Sem permissao para alterar configuracoes.")
                return redirect(f"{reverse('tenants:settings')}?tab=system")
            if settings_form.is_valid():
                settings_form.save()
                messages.success(request, "Configuracoes atualizadas.")
                return redirect(f"{reverse('tenants:settings')}?tab=system")
            active_tab = "system"
        elif action == "user_profile":
            profile_form = BusinessProfileForm(
                instance=business, can_edit_legal=is_owner
            )
            settings_form = BusinessSettingsForm(
                instance=business, can_edit_settings=is_owner
            )
            user_form = UserProfileForm(
                request.POST, request.FILES, instance=profile, user=request.user
            )
            password_form = UserPasswordForm(user=request.user)
            if user_form.is_valid():
                user = request.user
                user.first_name = user_form.cleaned_data.get("first_name", "")
                user.last_name = user_form.cleaned_data.get("last_name", "")
                user.save(update_fields=["first_name", "last_name"])
                user_form.save()
                messages.success(request, "Perfil atualizado.")
                return redirect(f"{reverse('tenants:settings')}?tab=user")
            active_tab = "user"
        elif action == "password":
            profile_form = BusinessProfileForm(
                instance=business, can_edit_legal=is_owner
            )
            settings_form = BusinessSettingsForm(
                instance=business, can_edit_settings=is_owner
            )
            user_form = UserProfileForm(instance=profile, user=request.user)
            password_form = UserPasswordForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password alterada.")
                return redirect(f"{reverse('tenants:settings')}?tab=security")
            active_tab = "security"
        else:
            profile_form = BusinessProfileForm(
                instance=business, can_edit_legal=is_owner
            )
            settings_form = BusinessSettingsForm(
                instance=business, can_edit_settings=is_owner
            )
            user_form = UserProfileForm(instance=profile, user=request.user)
            password_form = UserPasswordForm(user=request.user)
    else:
        profile_form = BusinessProfileForm(
            instance=business, can_edit_legal=is_owner
        )
        settings_form = BusinessSettingsForm(
            instance=business, can_edit_settings=is_owner
        )
        user_form = UserProfileForm(instance=profile, user=request.user)
        password_form = UserPasswordForm(user=request.user)

    return render(
        request,
        "tenants/settings.html",
        {
            "profile_form": profile_form,
            "settings_form": settings_form,
            "user_form": user_form,
            "password_form": password_form,
            "business": business,
            "is_owner": is_owner,
            "active_tab": active_tab,
            "wallets": wallets,
            "banks": banks,
        },
    )


@login_required
@business_required
@owner_required
def tenant_wallet_create(request):
    business = request.business
    if request.method == "POST":
        form = TenantMobileWalletForm(request.POST)
        if form.is_valid():
            wallet = form.save(commit=False)
            wallet.business = business
            wallet.created_by = request.user
            wallet.updated_by = request.user
            wallet.save()
            form = TenantMobileWalletForm()
            return render(
                request,
                "tenants/partials/payment_data_modal.html",
                {"form": form, "method_type": "wallet", "created": True},
            )
    else:
        form = TenantMobileWalletForm()
    return render(
        request,
        "tenants/partials/payment_data_modal.html",
        {"form": form, "method_type": "wallet"},
    )


@login_required
@business_required
@owner_required
def tenant_wallet_edit(request, wallet_id):
    wallet = get_object_or_404(
        TenantMobileWallet, id=wallet_id, business=request.business
    )
    if request.method == "POST":
        form = TenantMobileWalletForm(request.POST, instance=wallet)
        if form.is_valid():
            wallet = form.save(commit=False)
            wallet.updated_by = request.user
            wallet.save()
            return render(
                request,
                "tenants/partials/payment_data_modal.html",
                {"form": form, "method_type": "wallet", "updated": True},
            )
    else:
        form = TenantMobileWalletForm(instance=wallet)
    return render(
        request,
        "tenants/partials/payment_data_modal.html",
        {"form": form, "method_type": "wallet"},
    )


@login_required
@business_required
@owner_required
def tenant_bank_create(request):
    business = request.business
    if request.method == "POST":
        form = TenantBankAccountForm(request.POST)
        if form.is_valid():
            bank = form.save(commit=False)
            bank.business = business
            bank.created_by = request.user
            bank.updated_by = request.user
            bank.save()
            form = TenantBankAccountForm()
            return render(
                request,
                "tenants/partials/payment_data_modal.html",
                {"form": form, "method_type": "bank", "created": True},
            )
    else:
        form = TenantBankAccountForm()
    return render(
        request,
        "tenants/partials/payment_data_modal.html",
        {"form": form, "method_type": "bank"},
    )


@login_required
@business_required
@owner_required
def tenant_bank_edit(request, bank_id):
    bank = get_object_or_404(
        TenantBankAccount, id=bank_id, business=request.business
    )
    if request.method == "POST":
        form = TenantBankAccountForm(request.POST, instance=bank)
        if form.is_valid():
            bank = form.save(commit=False)
            bank.updated_by = request.user
            bank.save()
            return render(
                request,
                "tenants/partials/payment_data_modal.html",
                {"form": form, "method_type": "bank", "updated": True},
            )
    else:
        form = TenantBankAccountForm(instance=bank)
    return render(
        request,
        "tenants/partials/payment_data_modal.html",
        {"form": form, "method_type": "bank"},
    )


@login_required
@business_required
@owner_required
def tenant_payment_delete(request, kind, pk):
    if request.method != "POST":
        return redirect("tenants:settings")
    if kind == "wallet":
        obj = get_object_or_404(
            TenantMobileWallet, id=pk, business=request.business
        )
    else:
        obj = get_object_or_404(
            TenantBankAccount, id=pk, business=request.business
        )
    obj.delete()
    messages.success(request, "Dados removidos.")
    return redirect(f"{reverse('tenants:settings')}?tab=payments")


class TenantRegisterAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "tenant_register"
    authentication_classes = []

    def post(self, request):
        try:
            serializer = TenantRegisterSerializer(data=request.data)
        except ParseError:
            return Response(
                {"errors": {"non_field_errors": ["Payload invalido."]}, "detail": "Dados invalidos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not serializer.is_valid():
            detail_parts = []
            for field, messages in serializer.errors.items():
                if isinstance(messages, dict):
                    for sub_field, sub_messages in messages.items():
                        if sub_messages:
                            detail_parts.append(f"{sub_field}: {sub_messages[0]}")
                elif messages:
                    detail_parts.append(f"{field}: {messages[0]}")
            detail = "Dados invalidos."
            if detail_parts:
                detail = f"{detail} {', '.join(detail_parts)}"
            return Response(
                {"errors": serializer.errors, "detail": detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = serializer.save()
        business = result["business"]
        owner = result["owner"]
        return Response(
            {
                "tenant": {
                    "id": business.id,
                    "name": business.name,
                    "type": business.business_type,
                    "slug": business.slug,
                },
                "owner": {
                    "id": owner.id,
                    "email": owner.email,
                    "full_name": owner.get_full_name() or owner.username,
                },
                "next": {"login": True},
                "message": "Tenant created successfully",
            },
            status=status.HTTP_201_CREATED,
        )
