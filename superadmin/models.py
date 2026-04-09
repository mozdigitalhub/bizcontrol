from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from tenants.models import Business


class SubscriptionPlan(models.Model):
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    billing_cycle_months = models.PositiveIntegerField(default=1)
    trial_days = models.PositiveIntegerField(default=14)
    max_users = models.PositiveIntegerField(null=True, blank=True)
    max_branches = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    feature_flags = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_subscription_plans",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_subscription_plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TenantSubscription(models.Model):
    STATUS_TRIAL = "trial"
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_SUSPENDED = "suspended"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_TRIAL, "Trial"),
        (STATUS_ACTIVE, "Ativa"),
        (STATUS_EXPIRED, "Expirada"),
        (STATUS_SUSPENDED, "Suspensa"),
        (STATUS_CANCELED, "Cancelada"),
    ]

    PROOF_NONE = "none"
    PROOF_PENDING = "pending"
    PROOF_APPROVED = "approved"
    PROOF_REJECTED = "rejected"
    PROOF_CHOICES = [
        (PROOF_NONE, "Sem comprovativo"),
        (PROOF_PENDING, "Pendente"),
        (PROOF_APPROVED, "Aprovado"),
        (PROOF_REJECTED, "Rejeitado"),
    ]

    business = models.OneToOneField(
        Business, on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL)
    started_at = models.DateField(default=timezone.localdate)
    trial_ends_at = models.DateField(null=True, blank=True)
    ends_at = models.DateField(null=True, blank=True)
    next_renewal_at = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)
    payment_proof_status = models.CharField(
        max_length=20, choices=PROOF_CHOICES, default=PROOF_NONE
    )
    payment_reference = models.CharField(max_length=120, blank=True)
    last_payment_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tenant_subscriptions",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_tenant_subscriptions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["business__name"]
        indexes = [
            models.Index(fields=["status", "ends_at"]),
            models.Index(fields=["payment_proof_status"]),
        ]

    def __str__(self):
        return f"{self.business} - {self.get_status_display()}"

    @property
    def is_expiring_soon(self):
        if not self.ends_at:
            return False
        return self.ends_at <= timezone.localdate() + timedelta(days=7)


class TenantAdminNote(models.Model):
    TYPE_GENERAL = "general"
    TYPE_BILLING = "billing"
    TYPE_SUPPORT = "support"
    TYPE_RISK = "risk"
    TYPE_CHOICES = [
        (TYPE_GENERAL, "Geral"),
        (TYPE_BILLING, "Faturacao"),
        (TYPE_SUPPORT, "Suporte"),
        (TYPE_RISK, "Risco"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="superadmin_notes"
    )
    note_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_GENERAL)
    note = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tenant_admin_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["business", "created_at"])]

    def __str__(self):
        return f"{self.business} - {self.get_note_type_display()}"


class TenantStatusHistory(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="status_history"
    )
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    reason = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_status_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        indexes = [models.Index(fields=["business", "changed_at"])]

    def __str__(self):
        return f"{self.business}: {self.previous_status} -> {self.new_status}"


class SuperAdminAuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superadmin_audit_logs",
    )
    action = models.CharField(max_length=120)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=120, blank=True)
    business = models.ForeignKey(
        Business,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superadmin_audit_logs",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["action"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self):
        return self.action


class PlatformSetting(models.Model):
    key = models.SlugField(max_length=80, unique=True)
    value = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_platform_settings",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key


class PlatformAlert(models.Model):
    LEVEL_INFO = "info"
    LEVEL_WARNING = "warning"
    LEVEL_CRITICAL = "critical"
    LEVEL_CHOICES = [
        (LEVEL_INFO, "Informacao"),
        (LEVEL_WARNING, "Aviso"),
        (LEVEL_CRITICAL, "Critico"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="platform_alerts",
        null=True,
        blank=True,
    )
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default=LEVEL_INFO)
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_platform_alerts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_active", "level"])]

    def __str__(self):
        return self.title


class SupportTicket(models.Model):
    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_RESOLVED = "resolved"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Aberto"),
        (STATUS_IN_PROGRESS, "Em progresso"),
        (STATUS_RESOLVED, "Resolvido"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="support_tickets",
        null=True,
        blank=True,
    )
    subject = models.CharField(max_length=160)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_support_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return self.subject
