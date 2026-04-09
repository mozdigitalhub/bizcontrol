import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from billing.models import Invoice
from catalog.models import Product
from customers.models import Customer
from sales.models import Sale
from superadmin.decorators import superadmin_required
from superadmin.forms import (
    PlatformAlertForm,
    PlatformSettingForm,
    SuperAdminTenantCreateForm,
    SubscriptionPlanForm,
    SupportTicketForm,
    TenantAdminNoteForm,
    TenantSubscriptionForm,
)
from superadmin.models import (
    PlatformAlert,
    PlatformSetting,
    SubscriptionPlan,
    SuperAdminAuditLog,
    SupportTicket,
    TenantAdminNote,
    TenantSubscription,
)
from superadmin.services import (
    create_tenant_with_owner,
    extend_subscription,
    extend_trial,
    get_or_create_subscription,
    log_superadmin_action,
    resend_pending_tenant_email,
    set_payment_proof_status,
    transition_tenant_status,
)
from tenants.models import Business, BusinessMembership


def _month_series_map(queryset):
    return {
        row["month"].strftime("%Y-%m"): row["total"]
        for row in queryset
        if row.get("month")
    }


def _last_month_keys(months=6):
    today = timezone.localdate().replace(day=1)
    cursor = today
    keys = []
    for _ in range(months):
        keys.append(cursor.strftime("%Y-%m"))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    keys.reverse()
    return keys


@login_required
@superadmin_required
def dashboard(request):
    today = timezone.localdate()
    User = get_user_model()

    total_tenants = Business.objects.count()
    active_tenants = Business.objects.filter(status=Business.STATUS_ACTIVE).count()
    pending_tenants = Business.objects.filter(status=Business.STATUS_PENDING).count()
    total_users = User.objects.count()
    total_sales = Sale.objects.filter(status=Sale.STATUS_CONFIRMED).count()
    total_invoices = Invoice.objects.count()
    total_products = Product.objects.count()
    total_customers = Customer.objects.count()

    subscriptions = TenantSubscription.objects.select_related("plan", "business")
    trial_tenants = subscriptions.filter(status=TenantSubscription.STATUS_TRIAL).count()
    suspended_tenants = subscriptions.filter(
        status=TenantSubscription.STATUS_SUSPENDED
    ).count()
    expired_subscriptions = subscriptions.filter(
        Q(status=TenantSubscription.STATUS_EXPIRED)
        | Q(ends_at__lt=today, status=TenantSubscription.STATUS_ACTIVE)
    ).count()
    paying_tenants = subscriptions.filter(status=TenantSubscription.STATUS_ACTIVE).count()
    churn_tenants = subscriptions.filter(status=TenantSubscription.STATUS_CANCELED).count()

    mrr = subscriptions.filter(status=TenantSubscription.STATUS_ACTIVE).aggregate(
        total=Coalesce(Sum("plan__price_monthly"), Decimal("0"))
    )["total"]
    arr = mrr * Decimal("12")

    tenant_growth_qs = (
        Business.objects.annotate(month=TruncMonth("registered_at"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )
    tenant_growth_map = _month_series_map(tenant_growth_qs)
    month_keys = _last_month_keys(8)
    tenant_growth_values = [tenant_growth_map.get(key, 0) for key in month_keys]
    month_labels = [key[5:] + "/" + key[:4] for key in month_keys]

    status_map = dict(Business.STATUS_CHOICES)
    tenant_status_values = {
        status_map[key]: Business.objects.filter(status=key).count()
        for key in status_map
    }

    business_type_values = (
        Business.objects.values("business_type")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    business_type_labels = dict(Business.BUSINESS_TYPE_CHOICES)

    expiring_subscriptions = subscriptions.filter(
        status__in=[TenantSubscription.STATUS_ACTIVE, TenantSubscription.STATUS_TRIAL],
        ends_at__isnull=False,
        ends_at__lte=today + timedelta(days=14),
    ).order_by("ends_at")[:8]

    recent_registrations = Business.objects.order_by("-registered_at")[:6]
    recent_audits = SuperAdminAuditLog.objects.select_related("actor", "business")[:8]

    activities = []
    for business in recent_registrations:
        activities.append(
            {
                "when": business.registered_at,
                "label": f"Novo tenant registado: {business.name}",
                "type": "registration",
            }
        )
    for log in recent_audits:
        activities.append(
            {
                "when": log.created_at,
                "label": f"{log.action} ({log.business.name if log.business else 'global'})",
                "type": "audit",
            }
        )
    activities.sort(key=lambda item: item["when"], reverse=True)
    activities = activities[:12]

    alerts = PlatformAlert.objects.filter(is_active=True).order_by("-created_at")[:5]
    open_tickets = SupportTicket.objects.filter(
        status__in=[SupportTicket.STATUS_OPEN, SupportTicket.STATUS_IN_PROGRESS]
    ).count()
    users_inactive_30d = User.objects.filter(
        Q(last_login__isnull=True) | Q(last_login__lt=timezone.now() - timedelta(days=30))
    ).count()

    context = {
        "kpis": {
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "pending_tenants": pending_tenants,
            "trial_tenants": trial_tenants,
            "suspended_tenants": suspended_tenants,
            "expired_subscriptions": expired_subscriptions,
            "total_users": total_users,
            "total_sales": total_sales,
            "total_invoices": total_invoices,
            "total_products": total_products,
            "total_customers": total_customers,
            "paying_tenants": paying_tenants,
            "churn_tenants": churn_tenants,
            "mrr": mrr,
            "arr": arr,
            "open_tickets": open_tickets,
            "users_inactive_30d": users_inactive_30d,
        },
        "month_labels_json": json.dumps(month_labels),
        "tenant_growth_json": json.dumps(tenant_growth_values),
        "tenant_status_labels_json": json.dumps(list(tenant_status_values.keys())),
        "tenant_status_values_json": json.dumps(list(tenant_status_values.values())),
        "business_type_labels_json": json.dumps(
            [business_type_labels.get(item["business_type"], item["business_type"]) for item in business_type_values]
        ),
        "business_type_values_json": json.dumps([item["total"] for item in business_type_values]),
        "expiring_subscriptions": expiring_subscriptions,
        "activities": activities,
        "alerts": alerts,
    }
    return render(request, "superadmin/dashboard.html", context)


@login_required
@superadmin_required
def tenant_list(request):
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    tenant_type = (request.GET.get("type") or "").strip()
    subscription_status = (request.GET.get("subscription_status") or "").strip()
    sort = (request.GET.get("sort") or "registered_desc").strip()

    tenants = (
        Business.objects.select_related("subscription", "subscription__plan", "approved_by")
        .annotate(
            users_count=Count("memberships", distinct=True),
            products_count=Count("products", distinct=True),
            customers_count=Count("customers", distinct=True),
            invoices_count=Count("invoices", distinct=True),
            sales_count=Count("sales", distinct=True),
            last_access=Max("memberships__user__last_login"),
        )
    )

    if query:
        tenants = tenants.filter(
            Q(name__icontains=query)
            | Q(legal_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(city__icontains=query)
            | Q(slug__icontains=query)
        )
    if status:
        tenants = tenants.filter(status=status)
    if tenant_type:
        tenants = tenants.filter(business_type=tenant_type)
    if subscription_status:
        tenants = tenants.filter(subscription__status=subscription_status)

    if sort == "registered_asc":
        tenants = tenants.order_by("registered_at")
    elif sort == "name_asc":
        tenants = tenants.order_by("name")
    elif sort == "name_desc":
        tenants = tenants.order_by("-name")
    else:
        tenants = tenants.order_by("-registered_at")

    page = Paginator(tenants, 20).get_page(request.GET.get("page"))
    context = {
        "page": page,
        "query": query,
        "status": status,
        "tenant_type": tenant_type,
        "subscription_status": subscription_status,
        "sort": sort,
        "status_choices": Business.STATUS_CHOICES,
        "type_choices": Business.BUSINESS_TYPE_CHOICES,
        "subscription_choices": TenantSubscription.STATUS_CHOICES,
    }
    return render(request, "superadmin/tenant_list.html", context)


@login_required
@superadmin_required
def tenant_create(request):
    if request.method == "POST":
        form = SuperAdminTenantCreateForm(request.POST)
        if form.is_valid():
            business, owner, email_result = create_tenant_with_owner(
                data=form.cleaned_data,
                actor=request.user,
                request=request,
            )
            messages.success(
                request,
                f"Tenant {business.name} criado em estado pendente. Owner: {owner.email}.",
            )
            if email_result["attempted"]:
                if email_result["sent"]:
                    messages.success(request, "Email de registo pendente enviado ao owner.")
                else:
                    messages.warning(
                        request,
                        f"Tenant criado, mas o email falhou: {email_result['error'] or 'erro desconhecido'}.",
                    )
            return redirect("superadmin:tenant_detail", business_id=business.id)
        messages.error(request, "Revise os dados de criacao do tenant.")
    else:
        form = SuperAdminTenantCreateForm()
    context = {"form": form}
    return render(request, "superadmin/tenant_create.html", context)


@login_required
@superadmin_required
def tenant_approvals(request):
    pending = Business.objects.filter(status=Business.STATUS_PENDING).order_by("-registered_at")
    entries = []
    for business in pending:
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
        subscription = TenantSubscription.objects.filter(business=business).select_related("plan").first()
        entries.append(
            {
                "business": business,
                "owner": owner,
                "subscription": subscription,
            }
        )
    context = {
        "entries": entries,
        "pending_count": len(entries),
    }
    return render(request, "superadmin/tenant_approvals.html", context)


@login_required
@superadmin_required
def tenant_detail(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    subscription = get_or_create_subscription(business=business, actor=request.user)
    subscription_form = TenantSubscriptionForm(instance=subscription)
    note_form = TenantAdminNoteForm()

    memberships = (
        BusinessMembership.objects.filter(business=business)
        .select_related("user", "role_profile")
        .order_by("-created_at")
    )
    owner_membership = memberships.filter(role=BusinessMembership.ROLE_OWNER).first()
    owner = owner_membership.user if owner_membership else None
    owner_profile = getattr(owner, "profile", None) if owner else None

    onboarding_steps = {
        "owner_created": bool(owner),
        "password_updated": bool(owner_profile and not owner_profile.must_change_password),
        "welcome_seen": bool(owner_profile and owner_profile.welcome_seen),
        "onboarding_completed": bool(owner_profile and owner_profile.onboarding_completed),
    }
    onboarding_progress = int(
        (sum(1 for step in onboarding_steps.values() if step) / max(len(onboarding_steps), 1))
        * 100
    )

    context = {
        "business": business,
        "subscription": subscription,
        "subscription_form": subscription_form,
        "memberships": memberships[:20],
        "notes": business.superadmin_notes.select_related("created_by")[:20],
        "status_history": business.status_history.select_related("changed_by")[:20],
        "audit_logs": business.superadmin_audit_logs.select_related("actor")[:20],
        "note_form": note_form,
        "onboarding_steps": onboarding_steps,
        "onboarding_progress": onboarding_progress,
        "stats": {
            "users": memberships.count(),
            "products": business.products.count(),
            "customers": business.customers.count(),
            "sales": business.sales.count(),
            "invoices": business.invoices.count(),
            "last_access": memberships.aggregate(last=Max("user__last_login"))["last"],
        },
    }
    return render(request, "superadmin/tenant_detail.html", context)


@login_required
@superadmin_required
def tenant_status_action(request, business_id):
    if request.method != "POST":
        return redirect("superadmin:tenant_detail", business_id=business_id)
    business = get_object_or_404(Business, id=business_id)
    action = request.POST.get("action")
    reason = (request.POST.get("reason") or request.POST.get("note") or "").strip()
    try:
        _, temp_password, email_result = transition_tenant_status(
            business=business,
            action=action,
            actor=request.user,
            reason=reason,
            request=request,
        )
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        success_msg = "Estado do tenant atualizado."
        if temp_password:
            success_msg += f" Password temporaria gerada: {temp_password}"
        messages.success(request, success_msg)
        if email_result.get("attempted"):
            if email_result.get("sent"):
                messages.success(request, "Email transacional enviado com sucesso.")
            else:
                messages.warning(
                    request,
                    f"Estado atualizado, mas o email falhou: {email_result.get('error') or 'erro desconhecido'}.",
                )

    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("superadmin:tenant_detail", business_id=business_id)


@login_required
@superadmin_required
def tenant_resend_pending_email(request, business_id):
    if request.method != "POST":
        return redirect("superadmin:tenant_detail", business_id=business_id)

    business = get_object_or_404(Business, id=business_id)
    try:
        ok, error, temp_password, email_type = resend_pending_tenant_email(
            business=business,
            actor=request.user,
            request=request,
        )
        if ok:
            if email_type == "approved" and temp_password:
                messages.success(
                    request,
                    f"Email de acesso reenviado com sucesso. Nova password temporaria: {temp_password}",
                )
            elif email_type == "rejected":
                messages.success(request, "Email de rejeicao reenviado com sucesso.")
            else:
                messages.success(request, "Email de registo/subscricao reenviado com sucesso.")
        else:
            messages.error(request, f"Falha ao reenviar email: {error or 'erro desconhecido'}")
    except Exception as exc:
        messages.error(request, str(exc))

    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("superadmin:tenant_detail", business_id=business_id)


@login_required
@superadmin_required
def tenant_extend_trial(request, business_id):
    if request.method != "POST":
        return redirect("superadmin:tenant_detail", business_id=business_id)
    business = get_object_or_404(Business, id=business_id)
    days = request.POST.get("days") or "7"
    try:
        subscription = extend_trial(
            business=business,
            days=int(days),
            actor=request.user,
        )
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"Trial estendido ate {subscription.trial_ends_at}.",
        )
    return redirect("superadmin:tenant_detail", business_id=business_id)


@login_required
@superadmin_required
def tenant_extend_subscription(request, business_id):
    if request.method != "POST":
        return redirect("superadmin:tenant_detail", business_id=business_id)
    business = get_object_or_404(Business, id=business_id)
    days = request.POST.get("days") or "30"
    try:
        subscription = extend_subscription(
            business=business,
            days=int(days),
            actor=request.user,
        )
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"Assinatura estendida ate {subscription.ends_at}.",
        )
    return redirect("superadmin:tenant_detail", business_id=business_id)


@login_required
@superadmin_required
def tenant_subscription_update(request, business_id):
    if request.method != "POST":
        return redirect("superadmin:tenant_detail", business_id=business_id)
    business = get_object_or_404(Business, id=business_id)
    subscription = get_or_create_subscription(business=business, actor=request.user)
    form = TenantSubscriptionForm(request.POST, instance=subscription)
    if form.is_valid():
        subscription = form.save(commit=False)
        subscription.updated_by = request.user
        subscription.save()
        log_superadmin_action(
            actor=request.user,
            action="subscription.update",
            target_type="subscription",
            target_id=subscription.id,
            business=business,
            metadata={"status": subscription.status},
        )
        messages.success(request, "Assinatura atualizada.")
    else:
        messages.error(request, "Revise os dados da assinatura.")
    return redirect("superadmin:tenant_detail", business_id=business_id)


@login_required
@superadmin_required
def tenant_subscription_proof_action(request, business_id):
    if request.method != "POST":
        return redirect("superadmin:tenant_detail", business_id=business_id)
    business = get_object_or_404(Business, id=business_id)
    subscription = get_or_create_subscription(business=business, actor=request.user)
    proof_status = request.POST.get("proof_status", TenantSubscription.PROOF_PENDING)
    reference = (request.POST.get("payment_reference") or "").strip()
    set_payment_proof_status(
        subscription=subscription,
        proof_status=proof_status,
        actor=request.user,
        reference=reference,
    )
    messages.success(request, "Estado do comprovativo atualizado.")
    return redirect("superadmin:tenant_detail", business_id=business_id)


@login_required
@superadmin_required
def tenant_add_note(request, business_id):
    if request.method != "POST":
        return redirect("superadmin:tenant_detail", business_id=business_id)
    business = get_object_or_404(Business, id=business_id)
    form = TenantAdminNoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.business = business
        note.created_by = request.user
        note.save()
        log_superadmin_action(
            actor=request.user,
            action="tenant.add_note",
            target_type="business",
            target_id=business.id,
            business=business,
            metadata={"note_type": note.note_type},
        )
        messages.success(request, "Nota adicionada.")
    else:
        messages.error(request, "Nao foi possivel adicionar a nota.")
    return redirect("superadmin:tenant_detail", business_id=business_id)


@login_required
@superadmin_required
def subscriptions(request):
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    proof = (request.GET.get("proof") or "").strip()

    subs = TenantSubscription.objects.select_related("business", "plan").order_by(
        "business__name"
    )
    if query:
        subs = subs.filter(
            Q(business__name__icontains=query)
            | Q(business__slug__icontains=query)
            | Q(payment_reference__icontains=query)
        )
    if status:
        subs = subs.filter(status=status)
    if proof:
        subs = subs.filter(payment_proof_status=proof)

    page = Paginator(subs, 20).get_page(request.GET.get("page"))
    today = timezone.localdate()
    all_subs = TenantSubscription.objects.all()
    mrr = all_subs.filter(status=TenantSubscription.STATUS_ACTIVE).aggregate(
        total=Coalesce(Sum("plan__price_monthly"), Decimal("0"))
    )["total"]
    context = {
        "page": page,
        "query": query,
        "status": status,
        "proof": proof,
        "status_choices": TenantSubscription.STATUS_CHOICES,
        "proof_choices": TenantSubscription.PROOF_CHOICES,
        "cards": {
            "active": all_subs.filter(status=TenantSubscription.STATUS_ACTIVE).count(),
            "trial": all_subs.filter(status=TenantSubscription.STATUS_TRIAL).count(),
            "expired": all_subs.filter(status=TenantSubscription.STATUS_EXPIRED).count(),
            "suspended": all_subs.filter(status=TenantSubscription.STATUS_SUSPENDED).count(),
            "canceled": all_subs.filter(status=TenantSubscription.STATUS_CANCELED).count(),
            "paying": all_subs.filter(status=TenantSubscription.STATUS_ACTIVE).count(),
            "expiring_soon": all_subs.filter(
                status__in=[
                    TenantSubscription.STATUS_ACTIVE,
                    TenantSubscription.STATUS_TRIAL,
                ],
                ends_at__isnull=False,
                ends_at__lte=today + timedelta(days=7),
            ).count(),
            "mrr": mrr,
            "arr": mrr * Decimal("12"),
        },
    }
    return render(request, "superadmin/subscriptions.html", context)


@login_required
@superadmin_required
def plans(request):
    plan_id = request.GET.get("plan")
    selected_plan = None
    if plan_id:
        selected_plan = SubscriptionPlan.objects.filter(id=plan_id).first()

    if request.method == "POST":
        selected_plan = SubscriptionPlan.objects.filter(id=request.POST.get("plan_id")).first()
        form = SubscriptionPlanForm(request.POST, instance=selected_plan)
        if form.is_valid():
            plan = form.save(commit=False)
            if not selected_plan:
                plan.created_by = request.user
            plan.updated_by = request.user
            plan.save()
            if plan.is_default:
                SubscriptionPlan.objects.exclude(id=plan.id).update(is_default=False)
            log_superadmin_action(
                actor=request.user,
                action="plan.update" if selected_plan else "plan.create",
                target_type="plan",
                target_id=plan.id,
                metadata={"code": plan.code},
            )
            messages.success(request, "Plano guardado com sucesso.")
            return redirect(f"{request.path}?plan={plan.id}")
        messages.error(request, "Revise os dados do plano.")
    else:
        form = SubscriptionPlanForm(instance=selected_plan)

    context = {
        "plans": SubscriptionPlan.objects.order_by("name"),
        "form": form,
        "selected_plan": selected_plan,
    }
    return render(request, "superadmin/plans.html", context)


@login_required
@superadmin_required
def users(request):
    User = get_user_model()
    query = (request.GET.get("q") or "").strip()
    tenant_id = (request.GET.get("tenant") or "").strip()
    role = (request.GET.get("role") or "").strip()
    active = (request.GET.get("active") or "").strip()

    users_qs = User.objects.annotate(
        tenant_count=Count("business_memberships", distinct=True)
    ).order_by("-last_login", "-date_joined")
    if query:
        users_qs = users_qs.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    if tenant_id:
        users_qs = users_qs.filter(business_memberships__business_id=tenant_id)
    if role == "superadmin":
        users_qs = users_qs.filter(Q(is_superuser=True) | Q(groups__name="SuperAdmin"))
    elif role == "owner":
        users_qs = users_qs.filter(business_memberships__role=BusinessMembership.ROLE_OWNER)
    elif role == "staff":
        users_qs = users_qs.filter(business_memberships__role=BusinessMembership.ROLE_STAFF)
    if active == "yes":
        users_qs = users_qs.filter(is_active=True)
    elif active == "no":
        users_qs = users_qs.filter(is_active=False)

    page = Paginator(users_qs.distinct(), 25).get_page(request.GET.get("page"))
    latest_logins = (
        User.objects.filter(last_login__isnull=False).order_by("-last_login")[:10]
    )
    role_distribution = {
        "superadmin": User.objects.filter(
            Q(is_superuser=True) | Q(groups__name="SuperAdmin")
        )
        .distinct()
        .count(),
        "owner": User.objects.filter(
            business_memberships__role=BusinessMembership.ROLE_OWNER
        )
        .distinct()
        .count(),
        "staff": User.objects.filter(
            business_memberships__role=BusinessMembership.ROLE_STAFF
        )
        .distinct()
        .count(),
    }
    context = {
        "page": page,
        "query": query,
        "tenant_id": tenant_id,
        "role": role,
        "active": active,
        "tenants": Business.objects.order_by("name"),
        "latest_logins": latest_logins,
        "role_distribution": role_distribution,
    }
    return render(request, "superadmin/users.html", context)


@login_required
@superadmin_required
def user_toggle_active(request, user_id):
    if request.method != "POST":
        return redirect("superadmin:users")
    user = get_object_or_404(get_user_model(), id=user_id)
    if user.id == request.user.id:
        messages.error(request, "Nao pode desativar o proprio utilizador.")
        return redirect("superadmin:users")
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    log_superadmin_action(
        actor=request.user,
        action="user.toggle_active",
        target_type="user",
        target_id=user.id,
        metadata={"is_active": user.is_active},
    )
    messages.success(request, "Estado do utilizador atualizado.")
    return redirect("superadmin:users")


@login_required
@superadmin_required
def audit_logs(request):
    query = (request.GET.get("q") or "").strip()
    action = (request.GET.get("action") or "").strip()
    business_id = (request.GET.get("business") or "").strip()
    logs = SuperAdminAuditLog.objects.select_related("actor", "business")
    if query:
        logs = logs.filter(
            Q(action__icontains=query)
            | Q(target_type__icontains=query)
            | Q(target_id__icontains=query)
            | Q(actor__username__icontains=query)
        )
    if action:
        logs = logs.filter(action=action)
    if business_id:
        logs = logs.filter(business_id=business_id)
    page = Paginator(logs.order_by("-created_at"), 30).get_page(request.GET.get("page"))
    actions = (
        SuperAdminAuditLog.objects.exclude(action="")
        .values_list("action", flat=True)
        .distinct()
        .order_by("action")
    )
    context = {
        "page": page,
        "query": query,
        "action": action,
        "business_id": business_id,
        "actions": actions,
        "tenants": Business.objects.order_by("name"),
    }
    return render(request, "superadmin/audit_logs.html", context)


@login_required
@superadmin_required
def settings_page(request):
    setting_id = request.GET.get("setting")
    selected = PlatformSetting.objects.filter(id=setting_id).first() if setting_id else None
    if request.method == "POST":
        selected = PlatformSetting.objects.filter(id=request.POST.get("setting_id")).first()
        form = PlatformSettingForm(request.POST, instance=selected)
        if form.is_valid():
            item = form.save(commit=False)
            item.updated_by = request.user
            item.save()
            log_superadmin_action(
                actor=request.user,
                action="platform_setting.update" if selected else "platform_setting.create",
                target_type="platform_setting",
                target_id=item.id,
                metadata={"key": item.key},
            )
            messages.success(request, "Configuracao guardada.")
            return redirect(f"{request.path}?setting={item.id}")
        messages.error(request, "Revise os campos da configuracao.")
    else:
        form = PlatformSettingForm(instance=selected)

    context = {
        "form": form,
        "selected": selected,
        "settings": PlatformSetting.objects.order_by("key"),
        "business_types": Business.BUSINESS_TYPE_CHOICES,
    }
    return render(request, "superadmin/settings.html", context)


@login_required
@superadmin_required
def notifications(request):
    alert_id = request.GET.get("alert")
    ticket_id = request.GET.get("ticket")
    selected_alert = PlatformAlert.objects.filter(id=alert_id).first() if alert_id else None
    selected_ticket = SupportTicket.objects.filter(id=ticket_id).first() if ticket_id else None

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "alert":
            selected_alert = (
                PlatformAlert.objects.filter(id=request.POST.get("alert_id")).first()
            )
            alert_form = PlatformAlertForm(request.POST, instance=selected_alert)
            ticket_form = SupportTicketForm(instance=selected_ticket)
            if alert_form.is_valid():
                alert = alert_form.save(commit=False)
                if not selected_alert:
                    alert.created_by = request.user
                alert.save()
                log_superadmin_action(
                    actor=request.user,
                    action="alert.update" if selected_alert else "alert.create",
                    target_type="alert",
                    target_id=alert.id,
                    business=alert.business,
                    metadata={"level": alert.level, "active": alert.is_active},
                )
                messages.success(request, "Alerta guardado.")
                return redirect(f"{request.path}?alert={alert.id}")
            messages.error(request, "Revise os dados do alerta.")
        else:
            selected_ticket = (
                SupportTicket.objects.filter(id=request.POST.get("ticket_id")).first()
            )
            ticket_form = SupportTicketForm(request.POST, instance=selected_ticket)
            alert_form = PlatformAlertForm(instance=selected_alert)
            if ticket_form.is_valid():
                ticket = ticket_form.save(commit=False)
                if not selected_ticket:
                    ticket.created_by = request.user
                ticket.save()
                log_superadmin_action(
                    actor=request.user,
                    action="support_ticket.update" if selected_ticket else "support_ticket.create",
                    target_type="support_ticket",
                    target_id=ticket.id,
                    business=ticket.business,
                    metadata={"status": ticket.status},
                )
                messages.success(request, "Ticket guardado.")
                return redirect(f"{request.path}?ticket={ticket.id}")
            messages.error(request, "Revise os dados do ticket.")
    else:
        alert_form = PlatformAlertForm(instance=selected_alert)
        ticket_form = SupportTicketForm(instance=selected_ticket)

    context = {
        "alerts": PlatformAlert.objects.select_related("business").order_by("-created_at")[:50],
        "tickets": SupportTicket.objects.select_related("business", "assigned_to").order_by("-created_at")[:50],
        "alert_form": alert_form,
        "ticket_form": ticket_form,
        "selected_alert": selected_alert,
        "selected_ticket": selected_ticket,
    }
    return render(request, "superadmin/notifications.html", context)
