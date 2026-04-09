from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ParseError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from accounts.forms import UserPasswordForm, UserProfileForm
from accounts.models import UserProfile
from accounts.passwords import generate_temp_password
from tenants.decorators import _is_owner, business_required, owner_required
from tenants.forms import (
    BusinessProfileForm,
    BusinessSettingsForm,
    StaffForm,
    TenantBankAccountForm,
    TenantMobileWalletForm,
)
from tenants.models import (
    Business,
    BusinessMembership,
    RoleAuditLog,
    TenantBankAccount,
    TenantMobileWallet,
    TenantRole,
)
from tenants.permissions import tenant_permission_required
from tenants.rbac import (
    ensure_tenant_roles,
    get_permission_groups,
    reset_role_permissions,
)
from tenants.services import send_approved_email, send_pending_email, send_rejected_email
from tenants.serializers import TenantRegisterSerializer
from tenants.utils import get_default_business_membership


def _superuser_required(view_func):
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Sem permissao para esta area.")
            return redirect("reports:dashboard")
        return view_func(request, *args, **kwargs)

    return _wrapped


@login_required
def select_business(request):
    is_superuser = request.user.is_superuser
    memberships = None
    businesses = None
    if is_superuser:
        businesses = Business.objects.order_by("name")
    else:
        default_membership = get_default_business_membership(request.user)
        if default_membership:
            request.session["business_id"] = default_membership.business_id
            next_url = request.GET.get("next") or "reports:dashboard"
            return redirect(next_url)
        memberships = (
            BusinessMembership.objects.filter(
                user=request.user,
                is_active=True,
                business__status=Business.STATUS_ACTIVE,
            )
            .select_related("business")
            .order_by("business__name")
        )
        businesses = (
            Business.objects.filter(
                memberships__user=request.user,
                memberships__is_active=True,
                status=Business.STATUS_ACTIVE,
            )
            .distinct()
            .order_by("name")
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
def business_profile(request):
    business = request.business
    is_owner = _is_owner(request)
    owner_membership = (
        BusinessMembership.objects.filter(
            business=business,
            role=BusinessMembership.ROLE_OWNER,
            is_active=True,
        )
        .select_related("user")
        .first()
    )
    owner_email = (owner_membership.user.email or "").strip() if owner_membership else ""
    if request.method == "POST":
        form = BusinessProfileForm(
            request.POST,
            request.FILES,
            instance=business,
            can_edit_legal=is_owner,
            owner_email=owner_email,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil do negocio atualizado.")
            return redirect("tenants:business_profile")
    else:
        form = BusinessProfileForm(
            instance=business,
            can_edit_legal=is_owner,
            owner_email=owner_email,
        )
    return render(
        request,
        "tenants/business_profile.html",
        {"form": form, "business": business, "is_owner": is_owner},
    )


@login_required
@business_required
def tenant_payment_data(request):
    business = request.business
    is_owner = _is_owner(request)
    wallets = TenantMobileWallet.objects.filter(business=business).order_by("-is_active", "id")
    banks = TenantBankAccount.objects.filter(business=business).order_by("-is_active", "id")
    return render(
        request,
        "tenants/payment_data.html",
        {"business": business, "wallets": wallets, "banks": banks, "is_owner": is_owner},
    )


@login_required
@business_required
def user_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    membership = getattr(request, "membership", None)
    if request.method == "POST":
        action = request.POST.get("action", "profile")
        if action == "password":
            user_form = UserProfileForm(instance=profile, user=request.user)
            password_form = UserPasswordForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password alterada.")
                return redirect("tenants:user_profile")
        else:
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
                return redirect("tenants:user_profile")
    else:
        user_form = UserProfileForm(instance=profile, user=request.user)
        password_form = UserPasswordForm(user=request.user)
    return render(
        request,
        "tenants/user_profile.html",
        {
            "user_form": user_form,
            "password_form": password_form,
            "membership": membership,
        },
    )


@login_required
def force_password_change(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.must_change_password:
        return redirect("reports:dashboard")
    password_form = UserPasswordForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and password_form.is_valid():
        user = password_form.save()
        update_session_auth_hash(request, user)
        profile.must_change_password = False
        profile.temp_password_set_at = None
        profile.welcome_seen = False
        profile.onboarding_completed = False
        profile.save(
            update_fields=[
                "must_change_password",
                "temp_password_set_at",
                "welcome_seen",
                "onboarding_completed",
            ]
        )
        messages.success(request, "Password atualizada. Bem-vindo ao BizControl!")
        return redirect("reports:dashboard")
    return render(
        request,
        "registration/force_password_change.html",
        {"password_form": password_form},
    )


@login_required
def onboarding_welcome_seen(request):
    if request.method != "POST":
        return redirect("reports:dashboard")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.welcome_seen = True
    profile.save(update_fields=["welcome_seen"])
    return redirect("reports:dashboard")


@login_required
def onboarding_complete(request):
    if request.method != "POST":
        return redirect("reports:dashboard")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.onboarding_completed = True
    profile.save(update_fields=["onboarding_completed"])
    return redirect("reports:dashboard")


@login_required
@_superuser_required
def tenant_approvals(request):
    pending = Business.objects.filter(status=Business.STATUS_PENDING).order_by("created_at")
    entries = []
    for business in pending:
        owner_membership = (
            BusinessMembership.objects.filter(
                business=business, role=BusinessMembership.ROLE_OWNER
            )
            .select_related("user")
            .first()
        )
        owner = owner_membership.user if owner_membership else None
        entries.append(
            {
                "business": business,
                "owner": owner,
            }
        )
    return render(request, "tenants/tenant_approvals.html", {"entries": entries})


@login_required
@_superuser_required
def tenant_approve(request, business_id):
    if request.method != "POST":
        return redirect("tenants:tenant_approvals")
    business = get_object_or_404(Business, id=business_id)
    note = (request.POST.get("note") or "").strip()
    owner_membership = BusinessMembership.objects.filter(
        business=business, role=BusinessMembership.ROLE_OWNER
    ).select_related("user").first()
    owner = owner_membership.user if owner_membership else None
    if not owner:
        messages.error(request, "Nao foi possivel localizar o utilizador owner.")
        return redirect("tenants:tenant_approvals")
    temp_password = generate_temp_password()
    owner.set_password(temp_password)
    owner.save(update_fields=["password"])
    profile, _ = UserProfile.objects.get_or_create(user=owner)
    profile.must_change_password = True
    profile.temp_password_set_at = timezone.now()
    profile.welcome_seen = False
    profile.onboarding_completed = False
    profile.save(
        update_fields=[
            "must_change_password",
            "temp_password_set_at",
            "welcome_seen",
            "onboarding_completed",
        ]
    )

    business.status = Business.STATUS_ACTIVE
    business.approval_note = note
    business.approved_at = timezone.now()
    business.approved_by = request.user
    business.rejected_at = None
    business.rejected_by = None
    business.save(
        update_fields=[
            "status",
            "approval_note",
            "approved_at",
            "approved_by",
            "rejected_at",
            "rejected_by",
            "updated_at",
        ]
    )

    login_url = request.build_absolute_uri(reverse("login"))
    send_approved_email(
        business=business,
        owner=owner,
        temp_password=temp_password,
        login_url=login_url,
        approved_by=request.user,
    )
    messages.success(request, "Tenant aprovado e email enviado.")
    return redirect("tenants:tenant_approvals")


@login_required
@_superuser_required
def tenant_reject(request, business_id):
    if request.method != "POST":
        return redirect("tenants:tenant_approvals")
    business = get_object_or_404(Business, id=business_id)
    note = (request.POST.get("note") or "").strip()
    owner_membership = BusinessMembership.objects.filter(
        business=business, role=BusinessMembership.ROLE_OWNER
    ).select_related("user").first()
    owner = owner_membership.user if owner_membership else None
    business.status = Business.STATUS_REJECTED
    business.approval_note = note
    business.rejected_at = timezone.now()
    business.rejected_by = request.user
    business.save(
        update_fields=["status", "approval_note", "rejected_at", "rejected_by", "updated_at"]
    )
    if owner:
        send_rejected_email(
            business=business,
            owner=owner,
            rejected_by=request.user,
        )
    messages.success(request, "Tenant rejeitado.")
    return redirect("tenants:tenant_approvals")


@login_required
@business_required
@tenant_permission_required("tenants.manage_tax")
def system_settings(request):
    business = request.business
    can_edit = _is_owner(request) or request.user.is_superuser
    settings_form = BusinessSettingsForm(
        instance=business, can_edit_settings=can_edit
    )
    if request.method == "POST":
        settings_form = BusinessSettingsForm(
            request.POST, instance=business, can_edit_settings=can_edit
        )
        if settings_form.is_valid():
            settings_form.save()
            messages.success(request, "Configuracoes atualizadas.")
            return redirect("tenants:system_settings")
    return render(
        request,
        "tenants/system_settings.html",
        {"settings_form": settings_form, "business": business},
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
        return redirect("tenants:payment_data")
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
    return redirect("tenants:payment_data")


class TenantRegisterAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "tenant_register"
    authentication_classes = []

    def post(self, request):
        try:
            serializer = TenantRegisterSerializer(
                data=request.data,
                context={"registration_ip": _get_client_ip(request)},
            )
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
        send_pending_email(business=business, owner=owner, request=request)
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


def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


@login_required
@business_required
@tenant_permission_required("tenants.manage_staff")
def staff_list(request):
    business = request.business
    ensure_tenant_roles(business)
    memberships = (
        BusinessMembership.objects.filter(business=business)
        .select_related("user", "role_profile")
        .order_by("user__first_name", "user__last_name")
    )
    query = (request.GET.get("q") or "").strip()
    role_id = request.GET.get("role")
    status_filter = request.GET.get("status")
    if query:
        memberships = memberships.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
        )
    if role_id:
        memberships = memberships.filter(role_profile_id=role_id)
    if status_filter == "active":
        memberships = memberships.filter(is_active=True)
    elif status_filter == "inactive":
        memberships = memberships.filter(is_active=False)

    roles = TenantRole.objects.filter(business=business, is_active=True).order_by("name")
    return render(
        request,
        "tenants/staff_list.html",
        {
            "memberships": memberships.distinct(),
            "roles": roles,
            "filters": {
                "q": query,
                "role": role_id or "",
                "status": status_filter or "",
            },
        },
    )


@login_required
@business_required
@tenant_permission_required("tenants.manage_staff")
def staff_create(request):
    business = request.business
    ensure_tenant_roles(business)
    if request.method == "POST":
        form = StaffForm(request.POST, business=business)
        if form.is_valid():
            cleaned = form.cleaned_data
            email = cleaned.get("email")
            phone = cleaned.get("phone")
            username = email or phone
            User = get_user_model()
            password = cleaned.get("password") or generate_temp_password()
            user = User.objects.create_user(
                username=username,
                email=email or "",
                first_name=cleaned.get("first_name", ""),
                last_name=cleaned.get("last_name", ""),
                password=password,
            )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.phone = phone or ""
            profile.save(update_fields=["phone"])
            membership = BusinessMembership.objects.create(
                business=business,
                user=user,
                role=BusinessMembership.ROLE_STAFF,
                role_profile=cleaned.get("role_profile"),
                is_active=bool(cleaned.get("is_active")),
                department=cleaned.get("department", ""),
                notes=cleaned.get("notes", ""),
                created_by=request.user,
                updated_by=request.user,
            )
            membership.extra_permissions.set(cleaned.get("extra_permissions"))
            membership.revoked_permissions.set(cleaned.get("revoked_permissions"))
            RoleAuditLog.objects.create(
                business=business,
                target_type=RoleAuditLog.TARGET_USER,
                membership=membership,
                action=RoleAuditLog.ACTION_ASSIGN,
                payload={
                    "role": membership.role_profile.code if membership.role_profile else None,
                    "extra_permissions": [p.id for p in cleaned.get("extra_permissions")],
                    "revoked_permissions": [p.id for p in cleaned.get("revoked_permissions")],
                },
                changed_by=request.user,
            )
            if cleaned.get("password"):
                messages.success(request, "Colaborador criado com sucesso.")
            else:
                messages.success(request, f"Colaborador criado. Password temporaria: {password}")
            return redirect("tenants:staff_list")
    else:
        form = StaffForm(business=business)
    return render(
        request,
        "tenants/staff_form.html",
        {"form": form, "title": "Novo colaborador"},
    )


@login_required
@business_required
@tenant_permission_required("tenants.manage_staff")
def staff_edit(request, membership_id):
    business = request.business
    ensure_tenant_roles(business)
    membership = get_object_or_404(
        BusinessMembership.objects.select_related("user", "role_profile"),
        business=business,
        id=membership_id,
    )
    user = membership.user
    if request.method == "POST":
        form = StaffForm(
            request.POST,
            business=business,
            user_instance=user,
            membership_instance=membership,
        )
        if form.is_valid():
            cleaned = form.cleaned_data
            user.first_name = cleaned.get("first_name", "")
            user.last_name = cleaned.get("last_name", "")
            user.save(update_fields=["first_name", "last_name"])
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.phone = cleaned.get("phone") or profile.phone
            profile.save(update_fields=["phone"])
            membership.role_profile = cleaned.get("role_profile")
            membership.is_active = bool(cleaned.get("is_active"))
            membership.department = cleaned.get("department", "")
            membership.notes = cleaned.get("notes", "")
            membership.updated_by = request.user
            membership.save()
            membership.extra_permissions.set(cleaned.get("extra_permissions"))
            membership.revoked_permissions.set(cleaned.get("revoked_permissions"))
            RoleAuditLog.objects.create(
                business=business,
                target_type=RoleAuditLog.TARGET_USER,
                membership=membership,
                action=RoleAuditLog.ACTION_ASSIGN,
                payload={
                    "role": membership.role_profile.code if membership.role_profile else None,
                    "extra_permissions": [p.id for p in cleaned.get("extra_permissions")],
                    "revoked_permissions": [p.id for p in cleaned.get("revoked_permissions")],
                },
                changed_by=request.user,
            )
            messages.success(request, "Colaborador atualizado.")
            return redirect("tenants:staff_list")
    else:
        phone_value = ""
        if hasattr(user, "profile"):
            phone_value = user.profile.phone
        form = StaffForm(
            business=business,
            user_instance=user,
            membership_instance=membership,
            initial={
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": phone_value,
            },
        )
    return render(
        request,
        "tenants/staff_form.html",
        {
            "form": form,
            "title": "Editar colaborador",
            "membership": membership,
            "user": user,
            "effective_permissions": sorted(membership.get_effective_permission_keys()),
        },
    )


@login_required
@business_required
@tenant_permission_required("tenants.manage_staff")
def staff_toggle(request, membership_id):
    if request.method != "POST":
        return redirect("tenants:staff_list")
    membership = get_object_or_404(
        BusinessMembership, business=request.business, id=membership_id
    )
    membership.is_active = not membership.is_active
    membership.updated_by = request.user
    membership.save(update_fields=["is_active", "updated_by", "updated_at"])
    RoleAuditLog.objects.create(
        business=request.business,
        target_type=RoleAuditLog.TARGET_USER,
        membership=membership,
        action=RoleAuditLog.ACTION_ASSIGN,
        payload={"is_active": membership.is_active},
        changed_by=request.user,
    )
    messages.success(request, "Estado atualizado.")
    return redirect("tenants:staff_list")


@login_required
@business_required
@tenant_permission_required("tenants.manage_roles")
def roles_permissions(request):
    business = request.business
    ensure_tenant_roles(business)
    roles = TenantRole.objects.filter(business=business).order_by("name")
    role_id = request.GET.get("role") or (roles.first().id if roles else None)
    role = get_object_or_404(TenantRole, id=role_id, business=business) if role_id else None
    permission_groups = get_permission_groups()
    selected_perm_ids = set()
    if role:
        selected_perm_ids = set(role.permissions.values_list("id", flat=True))
    if request.method == "POST" and role:
        action = request.POST.get("action", "save")
        if action == "reset":
            reset_role_permissions(role, updated_by=request.user)
            RoleAuditLog.objects.create(
                business=business,
                target_type=RoleAuditLog.TARGET_ROLE,
                role=role,
                action=RoleAuditLog.ACTION_RESET,
                payload={"role": role.code},
                changed_by=request.user,
            )
            messages.success(request, "Perfil restaurado para o padrao.")
        else:
            perm_ids = request.POST.getlist("permissions")
            role.permissions.set(Permission.objects.filter(id__in=perm_ids))
            role.updated_by = request.user
            role.save(update_fields=["updated_by", "updated_at"])
            RoleAuditLog.objects.create(
                business=business,
                target_type=RoleAuditLog.TARGET_ROLE,
                role=role,
                action=RoleAuditLog.ACTION_UPDATE,
                payload={"permissions": perm_ids},
                changed_by=request.user,
            )
            messages.success(request, "Permissoes atualizadas.")
        return redirect(f"{reverse('tenants:roles')}?role={role.id}")

    return render(
        request,
        "tenants/roles_permissions.html",
        {
            "roles": roles,
            "selected_role": role,
            "permission_groups": permission_groups,
            "selected_perm_ids": selected_perm_ids,
        },
    )
