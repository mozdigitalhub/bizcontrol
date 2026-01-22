from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers

from accounts.signals import OWNER_GROUP
from finance.services import ensure_default_payment_methods
from accounts.models import UserProfile
from tenants.models import Business, BusinessMembership, TenantRole
from tenants.rbac import ensure_custom_permissions, ensure_tenant_roles


TENANT_TYPE_MAP = {
    "hardware": Business.BUSINESS_HARDWARE,
    "clothing": Business.BUSINESS_CLOTHING,
    "restaurant": Business.BUSINESS_RESTAURANT,
    "burger": Business.BUSINESS_BURGER,
    "mini_grocery": Business.BUSINESS_MINI_GROCERY,
    "electric": Business.BUSINESS_ELECTRIC,
    "workshop": Business.BUSINESS_WORKSHOP,
    "alcohol_stall": Business.BUSINESS_ALCOHOL,
}


def _build_unique_slug(name):
    base = slugify(name).strip("-")[:70] or "negocio"
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


def _ensure_owner_group():
    owner_group, _ = Group.objects.get_or_create(name=OWNER_GROUP)
    if owner_group.permissions.count() == 0:
        owner_group.permissions.set(Permission.objects.all())
    return owner_group


class TenantRegisterSerializer(serializers.Serializer):
    tenant_name = serializers.CharField(max_length=200)
    tenant_type = serializers.ChoiceField(choices=tuple(TENANT_TYPE_MAP.keys()))
    owner_full_name = serializers.CharField(max_length=150)
    owner_email = serializers.EmailField()
    owner_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    legal_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    nuit = serializers.CharField(max_length=30)
    commercial_registration = serializers.CharField(max_length=60, required=False, allow_blank=True)
    country = serializers.CharField(max_length=80, required=False, allow_blank=True)
    city = serializers.CharField(max_length=80, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    currency = serializers.CharField(max_length=10, required=False, default="MZN")
    timezone = serializers.CharField(max_length=60, required=False, default="Africa/Maputo")
    accept_terms = serializers.BooleanField()
    captcha = serializers.CharField(required=False, allow_blank=True)

    def validate_owner_email(self, value):
        User = get_user_model()
        if User.objects.filter(username__iexact=value).exists() or User.objects.filter(
            email__iexact=value
        ).exists():
            raise serializers.ValidationError("Nao foi possivel usar este email.")
        return value

    def validate_nuit(self, value):
        nuit = (value or "").strip().replace(" ", "")
        if not nuit:
            raise serializers.ValidationError("NUIT e obrigatorio.")
        if not nuit.isdigit() or len(nuit) != 9:
            raise serializers.ValidationError("NUIT deve ter 9 digitos.")
        if Business.objects.filter(nuit=nuit).exists():
            raise serializers.ValidationError("Este NUIT ja esta registado.")
        return nuit

    def validate_accept_terms(self, value):
        if value is not True:
            raise serializers.ValidationError("Tem de aceitar os termos.")
        return value

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("confirm_password"):
            raise serializers.ValidationError(
                {"confirm_password": ["As passwords nao coincidem."]}
            )
        try:
            password_validation.validate_password(attrs.get("password"))
        except Exception as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        User = get_user_model()
        tenant_name = validated_data["tenant_name"].strip()
        business_type = TENANT_TYPE_MAP[validated_data["tenant_type"]]
        owner_email = validated_data["owner_email"].strip().lower()
        first_name, last_name = _split_name(validated_data["owner_full_name"])
        registration_ip = (self.context.get("registration_ip") or "").strip()

        with transaction.atomic():
            slug = _build_unique_slug(tenant_name)
            business = Business.objects.create(
                name=tenant_name,
                legal_name=validated_data.get("legal_name", "").strip(),
                slug=slug,
                business_type=business_type,
                status=Business.STATUS_PENDING,
                phone=validated_data.get("owner_phone", ""),
                email=owner_email,
                nuit=validated_data.get("nuit"),
                commercial_registration=validated_data.get("commercial_registration", "").strip(),
                address=validated_data.get("address", ""),
                country=validated_data.get("country", ""),
                city=validated_data.get("city", ""),
                currency=validated_data.get("currency") or "MZN",
                timezone=validated_data.get("timezone") or "Africa/Maputo",
                modules_enabled=Business.MODULE_DEFAULTS.get(business_type, {}).copy(),
                feature_flags=Business.FEATURE_DEFAULTS.get(business_type, {}).copy(),
                registration_ip=registration_ip,
            )
            owner = User.objects.create_user(
                username=owner_email,
                email=owner_email,
                first_name=first_name,
                last_name=last_name,
                password=validated_data["password"],
            )
            UserProfile.objects.get_or_create(user=owner)
            _ensure_owner_group()
            ensure_custom_permissions()
            roles = ensure_tenant_roles(business, created_by=owner, force=True)
            owner_role = next(
                (role for role in roles if role.code == TenantRole.ROLE_OWNER_ADMIN),
                None,
            )
            BusinessMembership.objects.create(
                business=business,
                user=owner,
                role=BusinessMembership.ROLE_OWNER,
                role_profile=owner_role,
                created_by=owner,
                updated_by=owner,
            )
            ensure_default_payment_methods(business)
        return {"business": business, "owner": owner}
