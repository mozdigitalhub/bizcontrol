from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import UserProfile
from accounts.passwords import generate_temp_password
from finance.services import ensure_default_payment_methods
from superadmin.models import (
    SubscriptionPlan,
    SuperAdminAuditLog,
    TenantStatusHistory,
    TenantSubscription,
)
from tenants.models import Business, BusinessMembership, TenantEmailLog
from tenants.rbac import ensure_custom_permissions, ensure_tenant_roles
from tenants.services import send_approved_email, send_pending_email, send_rejected_email


def log_superadmin_action(
    *,
    actor=None,
    action,
    target_type="",
    target_id="",
    business=None,
    metadata=None,
):
    return SuperAdminAuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        business=business,
        metadata=metadata or {},
    )


def _default_plan():
    plan = SubscriptionPlan.objects.filter(is_active=True, is_default=True).first()
    if plan:
        return plan
    return SubscriptionPlan.objects.filter(is_active=True).order_by("id").first()


def _build_unique_slug(name):
    base = slugify((name or "").strip()).strip("-")[:70] or "negocio"
    slug = base
    suffix = 1
    while Business.objects.filter(slug=slug).exists():
        tail = f"-{suffix}"
        slug = f"{base[:70 - len(tail)]}{tail}"
        suffix += 1
    return slug


def _split_name(full_name):
    parts = (full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def get_or_create_subscription(*, business, actor=None):
    plan = _default_plan()
    today = timezone.localdate()
    defaults = {
        "plan": plan,
        "status": TenantSubscription.STATUS_TRIAL,
        "started_at": today,
        "trial_ends_at": today + timedelta(days=plan.trial_days if plan else 14),
        "next_renewal_at": today + timedelta(days=30),
        "created_by": actor,
        "updated_by": actor,
    }
    subscription, created = TenantSubscription.objects.get_or_create(
        business=business,
        defaults=defaults,
    )
    if not created and actor:
        changed = False
        if not subscription.plan and plan:
            subscription.plan = plan
            changed = True
        if changed:
            subscription.updated_by = actor
            subscription.save(update_fields=["plan", "updated_by", "updated_at"])
    return subscription


def create_tenant_with_owner(*, data, actor, request=None):
    user_model = get_user_model()
    owner_email = (data.get("owner_email") or "").strip().lower()
    owner_phone = (data.get("owner_phone") or "").strip()
    first_name, last_name = _split_name(data.get("owner_full_name"))
    business_type = data.get("business_type") or Business.BUSINESS_GENERAL

    with transaction.atomic():
        business = Business.objects.create(
            name=(data.get("name") or "").strip(),
            legal_name=(data.get("legal_name") or "").strip(),
            slug=_build_unique_slug(data.get("name")),
            business_type=business_type,
            status=Business.STATUS_PENDING,
            phone=(data.get("phone") or owner_phone).strip(),
            email=(data.get("email") or "").strip().lower(),
            nuit=(data.get("nuit") or "").strip() or None,
            commercial_registration=(data.get("commercial_registration") or "").strip(),
            address=(data.get("address") or "").strip(),
            country=(data.get("country") or "").strip(),
            city=(data.get("city") or "").strip(),
            timezone="Africa/Maputo",
            currency="MZN",
            modules_enabled=Business.MODULE_DEFAULTS.get(business_type, {}).copy(),
            feature_flags=Business.FEATURE_DEFAULTS.get(business_type, {}).copy(),
        )

        owner = user_model.objects.create_user(
            username=owner_email,
            email=owner_email,
            first_name=first_name,
            last_name=last_name,
        )
        owner.set_unusable_password()
        owner.save(update_fields=["password"])

        profile, _ = UserProfile.objects.get_or_create(user=owner)
        profile.phone = owner_phone
        profile.must_change_password = True
        profile.welcome_seen = False
        profile.onboarding_completed = False
        profile.save(
            update_fields=[
                "phone",
                "must_change_password",
                "welcome_seen",
                "onboarding_completed",
                "updated_at",
            ]
        )

        ensure_custom_permissions()
        roles = ensure_tenant_roles(business, created_by=actor, force=True)
        owner_role = next((role for role in roles if role.code == "owner_admin"), None)
        BusinessMembership.objects.create(
            business=business,
            user=owner,
            role=BusinessMembership.ROLE_OWNER,
            role_profile=owner_role,
            created_by=actor,
            updated_by=actor,
        )
        ensure_default_payment_methods(business)
        subscription = get_or_create_subscription(business=business, actor=actor)

        TenantStatusHistory.objects.create(
            business=business,
            previous_status="",
            new_status=Business.STATUS_PENDING,
            reason="Registo criado manualmente por SuperAdmin.",
            changed_by=actor,
        )
        log_superadmin_action(
            actor=actor,
            action="tenant.create",
            target_type="business",
            target_id=business.id,
            business=business,
            metadata={
                "owner_email": owner_email,
                "business_type": business.business_type,
                "subscription_status": subscription.status,
            },
        )

    email_result = {"attempted": False, "sent": None, "error": ""}
    if data.get("send_pending_email"):
        ok, error = send_pending_email(business=business, owner=owner, request=request)
        email_result = {"attempted": True, "sent": ok, "error": error or ""}

    return business, owner, email_result


def resend_pending_tenant_email(*, business, actor, request=None):
    owner_membership = (
        BusinessMembership.objects.filter(
            business=business,
            role=BusinessMembership.ROLE_OWNER,
            is_active=True,
        )
        .select_related("user")
        .first()
    )
    owner = owner_membership.user if owner_membership else None
    if not owner:
        raise ValueError("Nao foi possivel localizar o owner deste tenant.")

    temp_password = None
    email_type = TenantEmailLog.TYPE_PENDING
    if business.status == Business.STATUS_PENDING:
        ok, error = send_pending_email(business=business, owner=owner, request=request)
        email_type = TenantEmailLog.TYPE_PENDING
    elif business.status == Business.STATUS_ACTIVE:
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
        login_url = request.build_absolute_uri("/accounts/login/") if request else ""
        ok, error = send_approved_email(
            business=business,
            owner=owner,
            temp_password=temp_password,
            login_url=login_url,
            approved_by=actor,
        )
        email_type = TenantEmailLog.TYPE_APPROVED
    elif business.status == Business.STATUS_REJECTED:
        ok, error = send_rejected_email(business=business, owner=owner, rejected_by=actor)
        email_type = TenantEmailLog.TYPE_REJECTED
    else:
        raise ValueError("Estado atual nao suporta reenvio automatico de email.")

    log_superadmin_action(
        actor=actor,
        action="tenant.resend_status_email",
        target_type="business",
        target_id=business.id,
        business=business,
        metadata={
            "owner_email": owner.email,
            "email_type": email_type,
            "sent": ok,
            "error": error or "",
        },
    )
    return ok, (error or ""), temp_password, email_type


def transition_tenant_status(*, business, action, actor, reason="", request=None):
    action = (action or "").strip().lower()
    previous_status = business.status
    update_fields = ["status", "updated_at"]
    temp_password = None
    email_result = {"attempted": False, "sent": None, "error": "", "email_type": ""}

    if action == "approve":
        business.status = Business.STATUS_ACTIVE
        business.approval_note = reason
        business.approved_at = timezone.now()
        business.approved_by = actor
        business.rejected_at = None
        business.rejected_by = None
        update_fields.extend(
            [
                "approval_note",
                "approved_at",
                "approved_by",
                "rejected_at",
                "rejected_by",
            ]
        )
    elif action == "reject":
        business.status = Business.STATUS_REJECTED
        business.approval_note = reason
        business.rejected_at = timezone.now()
        business.rejected_by = actor
        update_fields.extend(["approval_note", "rejected_at", "rejected_by"])
    elif action in {"suspend", "deactivate"}:
        business.status = Business.STATUS_INACTIVE
    elif action in {"reactivate", "activate"}:
        business.status = Business.STATUS_ACTIVE
    elif action == "cancel":
        business.status = Business.STATUS_INACTIVE
    else:
        raise ValueError("Acao de status invalida.")

    business.save(update_fields=list(dict.fromkeys(update_fields)))

    owner_membership = (
        BusinessMembership.objects.filter(
            business=business, role=BusinessMembership.ROLE_OWNER, is_active=True
        )
        .select_related("user")
        .first()
    )
    owner = owner_membership.user if owner_membership else None

    if action == "approve" and previous_status == Business.STATUS_PENDING and owner:
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
        if request:
            login_url = request.build_absolute_uri("/accounts/login/")
            ok, error = send_approved_email(
                business=business,
                owner=owner,
                temp_password=temp_password,
                login_url=login_url,
                approved_by=actor,
            )
            email_result = {
                "attempted": True,
                "sent": ok,
                "error": error or "",
                "email_type": TenantEmailLog.TYPE_APPROVED,
            }
    elif action == "reject" and owner:
        ok, error = send_rejected_email(business=business, owner=owner, rejected_by=actor)
        email_result = {
            "attempted": True,
            "sent": ok,
            "error": error or "",
            "email_type": TenantEmailLog.TYPE_REJECTED,
        }

    subscription = TenantSubscription.objects.filter(business=business).first()
    if subscription:
        if action in {"suspend", "deactivate"}:
            subscription.status = TenantSubscription.STATUS_SUSPENDED
        elif action in {"reactivate", "activate", "approve"}:
            if subscription.status in {
                TenantSubscription.STATUS_SUSPENDED,
                TenantSubscription.STATUS_TRIAL,
                TenantSubscription.STATUS_EXPIRED,
            }:
                subscription.status = TenantSubscription.STATUS_ACTIVE
        elif action == "cancel":
            subscription.status = TenantSubscription.STATUS_CANCELED
        subscription.updated_by = actor
        subscription.save(update_fields=["status", "updated_by", "updated_at"])

    TenantStatusHistory.objects.create(
        business=business,
        previous_status=previous_status,
        new_status=business.status,
        reason=reason,
        changed_by=actor,
    )
    log_superadmin_action(
        actor=actor,
        action=f"tenant.{action}",
        target_type="business",
        target_id=business.id,
        business=business,
        metadata={
            "reason": reason,
            "previous_status": previous_status,
            "new_status": business.status,
            "email_attempted": email_result["attempted"],
            "email_sent": email_result["sent"],
            "email_type": email_result["email_type"],
            "email_error": email_result["error"],
        },
    )
    return business, temp_password, email_result


def extend_trial(*, business, days, actor):
    days = max(int(days), 1)
    subscription = get_or_create_subscription(business=business, actor=actor)
    today = timezone.localdate()
    baseline = subscription.trial_ends_at or today
    if baseline < today:
        baseline = today
    subscription.trial_ends_at = baseline + timedelta(days=days)
    subscription.status = TenantSubscription.STATUS_TRIAL
    subscription.updated_by = actor
    subscription.save(
        update_fields=["trial_ends_at", "status", "updated_by", "updated_at"]
    )
    log_superadmin_action(
        actor=actor,
        action="subscription.extend_trial",
        target_type="business",
        target_id=business.id,
        business=business,
        metadata={"days": days, "trial_ends_at": str(subscription.trial_ends_at)},
    )
    return subscription


def extend_subscription(*, business, days, actor):
    days = max(int(days), 1)
    subscription = get_or_create_subscription(business=business, actor=actor)
    today = timezone.localdate()
    baseline = subscription.ends_at or today
    if baseline < today:
        baseline = today
    subscription.ends_at = baseline + timedelta(days=days)
    subscription.next_renewal_at = subscription.ends_at
    if subscription.status in {
        TenantSubscription.STATUS_EXPIRED,
        TenantSubscription.STATUS_SUSPENDED,
        TenantSubscription.STATUS_TRIAL,
    }:
        subscription.status = TenantSubscription.STATUS_ACTIVE
    subscription.updated_by = actor
    subscription.save(
        update_fields=[
            "ends_at",
            "next_renewal_at",
            "status",
            "updated_by",
            "updated_at",
        ]
    )
    log_superadmin_action(
        actor=actor,
        action="subscription.extend",
        target_type="business",
        target_id=business.id,
        business=business,
        metadata={"days": days, "ends_at": str(subscription.ends_at)},
    )
    return subscription


def set_subscription_status(*, subscription, status, actor, reason=""):
    previous = subscription.status
    subscription.status = status
    subscription.updated_by = actor
    subscription.save(update_fields=["status", "updated_by", "updated_at"])
    log_superadmin_action(
        actor=actor,
        action="subscription.status_update",
        target_type="subscription",
        target_id=subscription.id,
        business=subscription.business,
        metadata={"previous_status": previous, "status": status, "reason": reason},
    )
    return subscription


def set_payment_proof_status(*, subscription, proof_status, actor, reference=""):
    subscription.payment_proof_status = proof_status
    if reference:
        subscription.payment_reference = reference
    subscription.updated_by = actor
    subscription.save(
        update_fields=[
            "payment_proof_status",
            "payment_reference",
            "updated_by",
            "updated_at",
        ]
    )
    log_superadmin_action(
        actor=actor,
        action="subscription.proof_update",
        target_type="subscription",
        target_id=subscription.id,
        business=subscription.business,
        metadata={"proof_status": proof_status, "reference": reference},
    )
    return subscription
